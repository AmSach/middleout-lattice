/**
 * geminiService.js v5 — Agada AI Service
 *
 * Key changes from v4:
 * - All Groq calls proxied through /api/groq (keys never sent to browser)
 * - Removed VITE_GROQ_KEY_* client-side key rotation
 * - Key rotation + model cascade still happen server-side in api/groq.js
 * - QR saltFromQR = ground truth, skips vision call entirely for that field
 * - Strict: if QR has salt, DB lookup uses ONLY that. Vision AI = fallback only.
 * - Parallel: vision + DB preload in parallel from start
 * - Pharmacy deep links for live prices (no CORS issues)
 */

import { ensureLoaded, lookupJanAushadhi, lookupCDSCO, buildSavingsSummary, parseSalts } from './dbService.js'
import { logAIResponse } from './debugLog.js'
import { batchFetchDavaIndiaPrices } from './davaIndiaService.js'

// ─── MODEL CASCADE ────────────────────────────────────────────────────────────
// Vision models — tried in order by api/groq.js proxy (server-side)
// NOTE: llama-3.2-*-vision-preview models are decommissioned as of 2025
// Use llama-4-scout for vision (validated working)
const VISION_MODELS = [
  'meta-llama/llama-4-scout-17b-16e-instruct',  // FASTEST, BEST FOR OCR - use this first
  'meta-llama/llama-4-maverick-17b-128e-instruct', // larger, better for complex labels
]
// Text-only models — for description + generics (no image)
const TEXT_MODELS = [
  'llama-3.3-70b-versatile',   // best quality
  'llama-3.1-70b-versatile',   // fallback
  'llama-3.1-8b-instant',      // fast fallback if others rate-limited
  'gemma2-9b-it',              // last resort
]

// ─── PROXY URL — all AI calls go through here, keys stay server-side ──────────
const GROQ_PROXY = '/api/groq'

// keyIndex unused — key rotation happens server-side in /api/groq
let keyIndex = 0

// ─── VISION PROMPT — lean, exact, fast ───────────────────────────────────────
const IMAGE_READ_PROMPT = `Medicine label reader. Extract ONLY what is printed. No advice.

SALT NAME: Drug name only, NO dose (e.g. "Amoxycillin" not "Amoxycillin 500mg"). Copy exactly.
DOSE: Numbers + unit only (e.g. "500mg" or "500mg + 125mg"). Use + to join multiple doses.
MULTILINE: Salt name and dose are often on separate lines or inside parentheses on the next line. Read across ALL lines — do not treat a line break as meaning the dose is absent. Example: "Mavyret\n(glecaprevir and pibrentasvir)\n100mg/40mg" → saltName="glecaprevir and pibrentasvir", doseStr="100mg/40mg".
DOSE SEPARATORS: doses may be separated by /, +, or commas — treat all as multi-dose. "100mg/40mg" = two doses.
If dose not visible on a MEDICINE or INJECTION label after reading ALL text on the image: doseStr=null, cannotRead=true, cannotReadReason="Dose not visible on label".
For TOPICAL, LIQUID, AYURVEDIC, SUPPLEMENT: dose is often absent by design — set doseStr=null but do NOT set cannotRead=true just because dose is missing.
If label totally unreadable: saltName=null, doseStr=null, confidence<50, cannotRead=true.
TORN/BLURRY/BOTTLE: Read what IS visible. cannotRead=true only if zero text legible.
BACK OF PACK / CONTENTS PAGE: If the image shows the back or side of a pack with an ingredients or composition table but no brand name — this is valid. Extract saltName and doseStr from the "Each tablet/capsule contains" or "Composition" section. List only the ACTIVE ingredients (ignore excipients like starch, lactose, magnesium stearate). Set brandName=null if not visible. Do NOT set cannotRead=true just because the front of the pack is not shown.
Damaged areas: ignore for fake signals.
productType: INJECTION for injections, LIQUID for oral liquids/syrups/drops, TOPICAL for gels/creams/ointments, MEDICINE for oral solids that are prescription or OTC pharmaceutical drugs.
Set productType=SUPPLEMENT for vitamins, minerals, calcium, vitamin D3, omega-3, multivitamins, nutraceuticals, health supplements — even if they come as tablets or strips (e.g. Calxofine D3, Shelcal, Neurobion, Limcee). These have no mg dose requirement.
Set productType=HAZARDOUS if the item is a dangerous non-medicine that should NOT be consumed — e.g. acids (hydrochloric acid, sulphuric acid, acetic acid), hydrogen peroxide (H2O2), bleach, caustic soda, industrial solvents, disinfectants, pesticides, drain cleaners. These are harmful if ingested or misused.
Set productType=NOT_MEDICINE if the item is clearly NOT a medicine and NOT hazardous — e.g. adhesives (Fevibond, Fevicol), cosmetics, food products, stationery, household items. When in doubt and there is no salt/drug name visible, use NOT_MEDICINE.

Genuine signals (only list if actually SEEN): hologram, QR/barcode, govt MRP sticker, tamper seal, batch no, expiry, full address+PIN, licence no
Fake signals (only list if actually SEEN): pixelated text on clear image, font mismatch, missing MRP/batch/expiry on INTACT label

JSON only, no markdown:
{"productType":"MEDICINE|INJECTION|LIQUID|TOPICAL|AYURVEDIC|SUPPLEMENT","brandName":null,"saltName":null,"doseStr":null,"manufacturer":null,"mrp":null,"unitSize":null,"batchNumber":null,"expiryDate":null,"licenceNumber":null,"genuineSignalsFound":[],"fakeSignalsFound":[],"confidence":85,"cannotRead":false,"cannotReadReason":null}`

// ─── MERGE SALT + DOSE ───────────────────────────────────────────────────────
// Recombines split saltName + doseStr fields from vision AI into "Salt Dose" string
function mergeSaltDose(saltName, doseStr) {
  if (!saltName) return null
  if (!doseStr) return saltName
  const salts = saltName.split(/\band\b|\+/i).map(s => s.trim()).filter(Boolean)
  const doses  = doseStr.split(/\+|,|\/|\band\b/i).map(d => d.trim()).filter(Boolean)
  if (salts.length === doses.length) return salts.map((s, i) => `${s} ${doses[i]}`).join(' and ')
  if (salts.length === 1 && doses.length === 1) return `${salts[0]} ${doses[0]}`
  // Count mismatch (e.g. 2 salts, doses split differently) — best effort: append full doseStr to first salt
  // Better to pass something through than silently drop the whole composition
  return `${saltName} ${doseStr}`
}

// ─── SCHEDULE H/H1/X OVERRIDE MAP ────────────────────────────────────────────
// Drugs that are commonly misclassified by AI. Ground truth from Indian drug schedules.
// Schedule H, H1, X = prescription required. OTC = false.
// This overrides whatever the AI says — not exhaustive, catches the most common errors.
const SCHEDULE_RX = new Set([
  // Schedule X (narcotics/psychotropics — always Rx)
  'alprazolam','clonazepam','diazepam','lorazepam','nitrazepam','triazolam',
  'midazolam','zolpidem','zopiclone','buprenorphine','tramadol','codeine',
  'morphine','oxycodone','fentanyl','pethidine','pentazocine','phenobarbitone',
  'phenobarbital','methylphenidate','modafinil',
  // Schedule H1 (high risk — always Rx)
  'amoxycillin','amoxicillin','azithromycin','ciprofloxacin','levofloxacin',
  'norfloxacin','ofloxacin','metronidazole','tinidazole','doxycycline',
  'clindamycin','cephalexin','cefixime','cefpodoxime','ceftriaxone','cefuroxime',
  'meropenem','piperacillin','vancomycin','rifampicin','isoniazid','ethambutol',
  'pyrazinamide','fluconazole','itraconazole','voriconazole','acyclovir',
  'oseltamivir','chloroquine','hydroxychloroquine','artemether','lumefantrine',
  'atorvastatin','rosuvastatin','simvastatin','metformin','glibenclamide',
  'glimepiride','sitagliptin','insulin','metoprolol','atenolol','amlodipine',
  'ramipril','enalapril','losartan','telmisartan','hydrochlorothiazide','furosemide',
  'frusemide','spironolactone','digoxin','warfarin','clopidogrel','aspirin',
  'atorvastatin','omeprazole','pantoprazole','rabeprazole','esomeprazole',
  'ondansetron','domperidone','metoclopramide','prednisolone','dexamethasone',
  'betamethasone','methylprednisolone','hydrocortisone','levothyroxine',
  'carbimazole','propylthiouracil','phenytoin','carbamazepine','valproate',
  'levetiracetam','gabapentin','pregabalin','amitriptyline','nortriptyline',
  'imipramine','fluoxetine','sertraline','escitalopram','paroxetine','venlafaxine',
  'duloxetine','mirtazapine','quetiapine','olanzapine','risperidone','haloperidol',
  'lithium','methotrexate','cyclophosphamide','imatinib','tamoxifen','letrozole',
  'norgestrel','ethinyloestradiol','ethinylestradiol','levonorgestrel','progesterone',
  'testosterone','sildenafil','tadalafil','vardenafil','finasteride','dutasteride',
  'allopurinol','colchicine','isotretinoin','acitretin','tacrolimus','cyclosporine',
  'mycophenolate','azathioprine','hydroxychloroquine','sulfasalazine','leflunomide',
])
const SCHEDULE_OTC = new Set([
  'paracetamol','ibuprofen','diclofenac','cetirizine','loratadine','fexofenadine',
  'levocetirizine','chlorpheniramine','diphenhydramine','antacid','ranitidine',
  'famotidine','dextromethorphan','guaifenesin','zinc','vitamin c','ascorbic acid',
  'vitamin d3','cholecalciferol','calcium','iron','folic acid','vitamin b12',
  'cyanocobalamin','vitamin b complex','multivitamin','magnesium','potassium',
  'oral rehydration','ors','povidone iodine','hydrogen peroxide','clotrimazole',
  'miconazole','terbinafine','permethrin','betadine','savlon',
])

function resolveRx(saltComposition, aiSaid) {
  if (!saltComposition) return aiSaid
  const s = saltComposition.toLowerCase()
  // Check Rx list first — if any known Rx salt appears, it's prescription
  for (const drug of SCHEDULE_RX) {
    if (s.includes(drug)) return true
  }
  // Check OTC list — if matches an OTC drug, it's not prescription
  for (const drug of SCHEDULE_OTC) {
    if (s.includes(drug)) return false
  }
  // Fall back to AI answer
  return aiSaid
}

// ─── DESCRIPTION PROMPT ───────────────────────────────────────────────────────
const mkDescPrompt = (brand, salt, type) =>
`Indian patient medicine info. Medicine: ${brand||'Unknown'} (${salt||'Unknown'}). Type: ${type||'MEDICINE'}.
PRESCRIPTION RULE: Set prescriptionRequired=true if this drug is Schedule H, H1, or X under Indian drug law (requires a doctor's prescription). Set false ONLY for genuinely OTC drugs (paracetamol, antacids, antihistamines, vitamins, minerals). When in doubt, set true.
No brand suggestions. General drug class only. JSON only:
{"whatItDoes":"2-3 plain sentences","howToTake":"general guidance","commonUses":["","",""],"prescriptionRequired":false,"sideEffects":["","",""],"importantWarnings":["",""],"overdoseRisk":"plain language","ayurvedicWarning":null,"supplementWarning":null,"doNotTakeWith":null}`

// ─── GENERICS PROMPT ─────────────────────────────────────────────────────────
const mkGenericsPrompt = (salt, productType) => {
  const routeRule = productType === 'INJECTION'
    ? 'ONLY injectable forms (vial/ampoule/IV). NEVER tablets or oral forms.'
    : productType === 'LIQUID'
    ? 'ONLY oral liquid forms (syrup/suspension/drops). NEVER tablets or injections.'
    : productType === 'TOPICAL'
    ? 'ONLY topical forms (gel/cream/ointment/lotion). NEVER oral or injectable forms.'
    : 'ONLY oral solid forms (tablets/capsules). NEVER injections or topicals.'
  return `You are an Indian pharmacist. Patient needs: ${salt}
List up to 3 real branded generics sold at Indian chemists containing EXACTLY this salt at EXACTLY this dose. Nothing else.
${routeRule}
STRICT RULES — violating any rule means the product must be excluded:
1. The "salt" field in your response MUST be exactly: ${salt}
2. NEVER include a product unless you are certain it contains ${salt} as its ONLY active ingredient(s).
3. If a brand name sounds similar but contains a different salt — EXCLUDE IT.
4. If you are not sure a product is real — EXCLUDE IT. Return 1 item rather than fabricate 2 or 3.
5. EACH item must be from a DIFFERENT manufacturer.
Use prices from Netmeds, Apollo Pharmacy, 1mg, DavaIndia as reference.
Manufacturers: Cipla, Sun Pharma, Dr Reddy's, Lupin, Mankind, Alkem, Intas, Zydus, Abbott India, Torrent, Glenmark, Micro Labs, FDC, Macleods, Aristo, Cadila, Hetero, Alembic, Ipca.
JSON array only, no markdown, 1-3 items:
[{"name":"Full Brand Name Strength","brand":"Manufacturer","salt":"${salt}","packSize":"10 tablets","estimatedMrp":25,"perUnit":2.5,"availableAt":"Any chemist","isJanAushadhi":false,"aiEstimated":true}]`
}

// ─── PHARMACY DEEP LINKS ─────────────────────────────────────────────────────
// Full salt+dose in query so user lands on the right strength, not just the salt
export function pharmacyLinks(saltComposition) {
  if (!saltComposition) return []
  const q = encodeURIComponent(saltComposition)
  return [
    { name: 'Netmeds',   url: `https://www.netmeds.com/products/?q=${q}` },
    { name: 'Apollo',    url: `https://www.apollopharmacy.in/search-medicines/${q}` },
    { name: '1mg',       url: `https://www.1mg.com/search/all?name=${q}` },
    { name: 'DavaIndia', url: `https://www.davaindia.com/search/all?search=${q}` },
  ]
}

// ─── MAIN SCAN ────────────────────────────────────────────────────────────────
export async function scanMedicine(imageBase64, mimeType = 'image/jpeg', barcodeData = null) {

  // Start DB load immediately — parallel with everything else
  const dbPromise = ensureLoaded().catch(() => {})

  // ── GROUND TRUTH from QR ──────────────────────────────────────────────────
  // If QR has salt: this IS the correct composition. Vision AI cannot override it.
  const qrSalt     = barcodeData?.saltFromQR  || null
  const qrBrand    = barcodeData?.brandFromQR || null
  const qrBatch    = barcodeData?.batchNumber || null
  const qrExpiry   = barcodeData?.expiryDate  || null
  const qrMrp      = barcodeData?.mrpFromQR   || null

  // ── Phase 1: Vision AI reads label ───────────────────────────────────────
  // If QR already gave us salt+brand, we still call vision for:
  //   manufacturer, unitSize, mrp, batch (if not in QR), authenticity signals
  // But we cap tokens lower since less work needed
  const img = await callVision(imageBase64, mimeType, IMAGE_READ_PROMPT)

  // ── Hard block: not a medicine ───────────────────────────────────────────
  // If the AI identifies this as a non-medicine product (adhesive, cosmetic,
  // food, household chemical etc.) — stop immediately, return a clear rejection.
  // ── Hard block: hazardous substance ──────────────────────────────────────
  // If the AI identifies this as a dangerous chemical (acid, H2O2, bleach etc.)
  // — stop immediately with a DANGER warning. Never show medicine info for these.
  if (img.productType === 'HAZARDOUS') {
    return {
      productType:     'HAZARDOUS',
      brandName:       img.brandName || null,
      saltComposition: null,
      manufacturer:    img.manufacturer || null,
      mrp:             null,
      unitSize:        null,
      batchNumber:     null,
      expiryDate:      null,
      isExpired:       false,
      licenceNumber:   null,
      confidence:      img.confidence || 90,
      saltSource:      'AI_VISION',
      cannotRead:      true,
      cannotReadReason: '⚠️ DANGER: This appears to be a hazardous chemical — NOT a medicine. Do NOT consume or ingest this product. Keep away from children. In case of accidental ingestion, call Poison Control: 1800-116-117 (India, free).',
      authenticity:    { status: 'CANNOT_DETERMINE', reason: 'Hazardous substance — not a medicine.', genuineSignalsFound: [], fakeSignalsFound: [], cdscoBadge: null, warning: '⚠️ HAZARDOUS SUBSTANCE — NOT FOR CONSUMPTION' },
      medicineInfo:    null,
      alternatives:    { hasGenerics: false, topAlternatives: [], pharmacyLinks: [] },
      dataSource:      { salt: 'N/A', alts: 'N/A', cdsco: 'N/A', cdscoFound: false },
    }
  }

  if (img.productType === 'NOT_MEDICINE') {
    return {
      productType:     'NOT_MEDICINE',
      brandName:       img.brandName || null,
      saltComposition: null,
      manufacturer:    img.manufacturer || null,
      mrp:             null,
      unitSize:        null,
      batchNumber:     null,
      expiryDate:      null,
      isExpired:       false,
      licenceNumber:   null,
      confidence:      img.confidence || 90,
      saltSource:      'AI_VISION',
      cannotRead:      true,
      cannotReadReason: 'This does not appear to be a medicine. Agada only works with pharmaceutical products.',
      authenticity:    { status: 'CANNOT_DETERMINE', reason: 'Not a medicine.', genuineSignalsFound: [], fakeSignalsFound: [], cdscoBadge: null, warning: null },
      medicineInfo:    null,
      alternatives:    { hasGenerics: false, topAlternatives: [], pharmacyLinks: [] },
      dataSource:      { salt: 'N/A', alts: 'N/A', cdsco: 'N/A', cdscoFound: false },
    }
  }


  // Reconstruct salt from separated saltName + doseStr fields
  const mergedSalt  = mergeSaltDose(img.saltName, img.doseStr)
  const finalSalt   = qrSalt   || mergedSalt
  const finalBrand  = qrBrand  || img.brandName
  const finalBatch  = qrBatch  || img.batchNumber
  const finalExpiry = qrExpiry || img.expiryDate
  const finalMrp    = qrMrp    || img.mrp

  // Dose gate: behaviour depends on product type
  // MEDICINE/INJECTION — dose is safety-critical for alternatives, but many Indian packs
  //   only print the dose on the back panel. If salt is clearly readable we proceed —
  //   alternatives lookup uses salt-only which is still valid and safe.
  // TOPICAL/LIQUID/AYURVEDIC/SUPPLEMENT — dose is often absent by design (e.g. "apply as needed"),
  //   so we always allow lookup without a dose number.
  const typeNeedsDose = !img.productType || img.productType === 'MEDICINE' || img.productType === 'INJECTION'
  const hasDoseNumber = /\d+\s*(mg|mcg|g|iu)/i.test(finalSalt || '') || /\d+\s*(mg|mcg|g|iu)/i.test(img.doseStr || '')
  const hasSalt       = !!(finalSalt && finalSalt.trim().length > 3)
  // doseConfirmed = true when:
  //   - QR gave us the salt (ground truth), OR
  //   - dose number is visible in the extracted text, OR
  //   - product type doesn't need a dose (topical/supplement/etc.), OR
  //   - salt is clearly readable (front-of-pack; dose may be on back — still scannable)
  const doseConfirmed = !!qrSalt || hasDoseNumber || !typeNeedsDose || hasSalt

  // Only block if we have NO salt AND no dose — truly unreadable label
  if (!doseConfirmed && !hasSalt) {
    img.cannotRead = true
    img.cannotReadReason = img.cannotReadReason || 'Could not read medicine name or dose. Try scanning a clearer image or the barcode.'
  } else {
    // Salt is readable — clear any erroneous "dose not visible" block the AI may have set
    if (img.cannotRead && img.cannotReadReason && /dose/i.test(img.cannotReadReason)) {
      img.cannotRead = false
      img.cannotReadReason = null
    }
  }

  if (qrSalt) {
    img.genuineSignalsFound = [...(img.genuineSignalsFound || []), 'QR/barcode decoded — salt verified']
  }

  const expiryStr = finalExpiry
  const isExpired = expiryStr ? checkExpired(expiryStr) : false

  await dbPromise

  // ── Phase 2: DB lookup — only when dose is confirmed ──────────────────────
  const jaLookup    = doseConfirmed ? lookupJanAushadhi(finalSalt, finalMrp, img.unitSize) : { best: null, doseMismatch: null, noDose: false }
  const cdscoResult = lookupCDSCO(finalSalt)
  const jaBest      = jaLookup.best
  const jaDoseDiff  = jaLookup.doseMismatch

  // ── Phase 3: description + up to 3 branded generics (parallel) ───────────
  let info = null, aiGenerics = []
  if (finalSalt || finalBrand) {
    const [infoRes, genRes] = await Promise.allSettled([
      callText(mkDescPrompt(finalBrand, finalSalt, img.productType)),
      (finalSalt && doseConfirmed) ? callText(mkGenericsPrompt(finalSalt, img.productType)) : Promise.resolve(null),
    ])
    info = infoRes.status === 'fulfilled' ? infoRes.value : null
    // Override AI's prescriptionRequired with ground truth from schedule map
    if (info) info.prescriptionRequired = resolveRx(finalSalt, info.prescriptionRequired)
    if (genRes.status === 'fulfilled' && Array.isArray(genRes.value)) {
      // Extract primary drug names from the query salt for validation
      // e.g. "Flunarizine 10mg" → ["flunarizine"]
      const queryDrugNames = (finalSalt || '')
        .toLowerCase()
        .split(/\band\b|\+|,/i)
        .map(s => s.replace(/\d+\s*(mg|mcg|g|iu|ml)/gi, '').trim())
        .filter(s => s.length > 3)

      const seen = new Set()
      aiGenerics = genRes.value
        .filter(g => g && g.name && g.brand)
        // Salt validation: the returned salt field must contain all primary drug names
        // This catches hallucinations like "Flumark" (different salt) for "Flunarizine"
        .filter(g => {
          if (!queryDrugNames.length) return true
          const returnedSalt = (g.salt || '').toLowerCase()
          const returnedName = (g.name || '').toLowerCase()
          // Every query drug name must appear in EITHER the salt field or the product name
          // If salt field is wrong/missing, check name as fallback
          return queryDrugNames.every(drug =>
            returnedSalt.includes(drug) || returnedName.includes(drug)
          )
        })
        // Deduplicate by manufacturer
        .filter(g => {
          const key = (g.brand || '').toLowerCase()
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        .slice(0, 3)
    }
  }

  // 1 JA verified + up to 3 AI-estimated branded generics
  let allAlts = [
    ...(jaBest ? [jaBest] : []),
    ...aiGenerics,
  ]

  // ── DavaIndia live price enrichment ──────────────────────────────────────
  // Fetch real prices from DavaIndia for each alternative in parallel.
  // If a price comes back, it replaces the AI-estimated price and marks the
  // entry as highConfidence=true with priceSource='DavaIndia'.
  // Gracefully degrades — if proxy is down, allAlts stay as-is.
  if (allAlts.length > 0) {
    try {
      const davaMap = await batchFetchDavaIndiaPrices(allAlts)
      allAlts = allAlts.map(alt => {
        const key = alt.salt || alt.name
        const dava = davaMap.get(key)
        if (!dava) return alt  // no DavaIndia result — keep AI estimate as-is
        return {
          ...alt,
          // Override price fields with DavaIndia live data
          mrp:           dava.mrp,
          estimatedMrp:  dava.mrp,
          packSize:      dava.packSize || alt.packSize,
          perUnit:       dava.perUnit  ?? alt.perUnit,
          // Source & confidence flags
          priceSource:   'DavaIndia',
          highConfidence: true,
          aiEstimated:   false,  // it's a real price now, not AI estimated
          davaIndiaName: dava.name,  // actual product name on DavaIndia
        }
      })
    } catch {
      // batchFetch should never throw, but belt-and-suspenders
    }
  }

  const authenticity = buildAuthenticity(img, cdscoResult, isExpired, barcodeData, qrSalt)
  if ((img.confidence || 0) < 50 && !qrSalt) {
    authenticity.status  = 'CANNOT_DETERMINE'
    authenticity.warning = ((authenticity.warning || '') + ' Low confidence — verify with pharmacist.').trim()
  }

  // Flag when salt is readable but dose is absent (e.g. dose printed on back of pack only)
  const doseUnconfirmed = hasSalt && !hasDoseNumber && !qrSalt && typeNeedsDose

  return {
    productType:     img.productType || 'MEDICINE',
    brandName:       finalBrand,
    saltComposition: finalSalt,
    manufacturer:    img.manufacturer,
    mrp:             finalMrp,
    unitSize:        img.unitSize,
    batchNumber:     finalBatch,
    expiryDate:      expiryStr,
    isExpired,
    licenceNumber:   img.licenceNumber,
    confidence:      qrSalt ? 99 : (img.confidence || 70),
    saltSource:      qrSalt ? 'QR_BARCODE' : 'AI_VISION',
    doseUnconfirmed,
    cannotRead:      img.cannotRead || false,
    cannotReadReason:img.cannotReadReason || null,
    authenticity,
    medicineInfo:    info || fallbackInfo(img.productType),
    alternatives: {
      hasGenerics:          allAlts.length > 0,
      janAushadhiAvailable: !!jaBest,
      topAlternatives:      allAlts,
      doseMismatchAlt:      jaDoseDiff,   // singular — one dose-mismatch at most
      jaCount:              jaBest ? 1 : 0,
      savingsSummary:       buildSavingsSummary(jaBest, finalMrp, img.unitSize),
      pharmacyLinks:        pharmacyLinks(finalSalt),
      whereToFind:          'Jan Aushadhi Kendras — janaushadhi.gov.in · 1800-180-8080',
      disclaimer:           'Jan Aushadhi prices from official BPPI database. HIGH CONFIDENCE prices are sourced live from DavaIndia. AI ESTIMATED prices are approximate — verify at the chemist.',
    },
    dataSource: {
      salt:       qrSalt ? 'QR barcode (verified)' : 'AI vision (estimated)',
      alts:       'BPPI Jan Aushadhi DB + AI',
      cdsco:      cdscoResult.found ? 'CDSCO Drug Registry' : 'Not in CDSCO registry',
      cdscoFound: cdscoResult.found,
    }
  }
}

// ─── AUTHENTICITY ─────────────────────────────────────────────────────────────
function buildAuthenticity(img, cdsco, isExpired, barcode, qrSalt) {
  const genuine = img.genuineSignalsFound || []
  const fake    = img.fakeSignalsFound    || []

  if (isExpired) return {
    status: 'CANNOT_DETERMINE',
    reason: `Medicine appears expired (${img.expiryDate}).`,
    genuineSignalsFound: genuine, fakeSignalsFound: [...fake, 'Expired'],
    cdscoBadge: cdsco.badge || null, cdscoIndication: cdsco.indication || null,
    warning: '⚠ Expired. Do not consume.',
  }

  const score = genuine.length * 18 - fake.length * 25 + (cdsco.found ? 20 : 0) + (barcode ? 15 : 0) + (qrSalt ? 20 : 0)
  const status = fake.length >= 2 || score < -20 ? 'LIKELY_FAKE'
    : score >= 30 || genuine.length >= 2           ? 'LIKELY_GENUINE'
    : 'CANNOT_DETERMINE'

  return {
    status,
    reason: [
      genuine.length ? `Genuine signals: ${genuine.join(', ')}` : '',
      fake.length    ? `Suspicious: ${fake.join(', ')}` : '',
      !genuine.length && !fake.length ? 'Insufficient visual evidence.' : '',
    ].filter(Boolean).join(' | '),
    genuineSignalsFound: genuine,
    fakeSignalsFound:    fake,
    cdscoBadge:      cdsco.badge || (
      img.productType === 'AYURVEDIC'  ? '🌿 Regulated by AYUSH, not CDSCO.' :
      img.productType === 'SUPPLEMENT' ? 'Dietary supplement — not CDSCO scheduled.' :
      'Salt not found in CDSCO registry.'
    ),
    cdscoIndication:  cdsco.indication || null,
    cdscoFound:       cdsco.found,
    approvalDate:     cdsco.approvalDate || null,
    warning: fake.length ? 'Return to chemist. Report fakes: 1800-180-3024 (free).' : null,
  }
}

// ─── GROQ CALLERS ─────────────────────────────────────────────────────────────
// For each model, ALL keys are tried before moving to the next model.
// This ensures a decommissioned/rate-limited model doesn't silently kill the
// cascade — every backup model gets a fair shot with every available key.

async function callVision(b64, mime, prompt) {
  // Keys are managed server-side in /api/groq — no client-side keys needed
  let lastErr = 'no models available'
  const t0 = Date.now()
  for (const model of VISION_MODELS) {
    try {
      const res = await fetch(GROQ_PROXY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model, max_tokens: 600, temperature: 0.05,
          messages: [{ role: 'user', content: [
            { type: 'text', text: prompt },
            { type: 'image_url', image_url: { url: `data:${mime};base64,${b64}` } }
          ]}]
        })
      })
      if (res.status === 429) { lastErr = `${model} rate-limited`; continue } // proxy exhausted all keys — try next model
      if (res.status === 404) { lastErr = `${model} decommissioned`; continue } // model gone — try next model
      if (!res.ok) { const e = await res.json().catch(()=>({})); lastErr = e?.error?.message || `${res.status}`; continue }
      const data = await res.json()
      const rawResponse = data?.choices?.[0]?.message?.content
      const parsed = safeJSON(rawResponse)
      logAIResponse({ phase: 'vision', prompt, rawResponse, parsed, durationMs: Date.now()-t0 })
      if (parsed) return parsed
      lastErr = 'JSON parse fail'
    } catch(e) {
      lastErr = e.message
    }
  }
  throw new Error(`Could not read image: ${lastErr}`)
}

async function callText(prompt) {
  // Keys are managed server-side in /api/groq — no client-side keys needed
  let lastErr = 'no models'
  const t0 = Date.now()
  const phase = prompt.includes('pharmacist') ? 'generics' : 'description'
  for (const model of TEXT_MODELS) {
    try {
      const res = await fetch(GROQ_PROXY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, max_tokens: 800, temperature: 0.1, messages: [{ role: 'user', content: prompt }] })
      })
      if (res.status === 429) { lastErr = `${model} rate-limited`; continue } // proxy exhausted all keys — try next model
      if (res.status === 404) { lastErr = `${model} decommissioned`; continue } // model gone — try next model
      if (!res.ok) { lastErr = `${res.status}`; continue }
      const data = await res.json()
      const rawResponse = data?.choices?.[0]?.message?.content
      const parsed = safeJSON(rawResponse)
      logAIResponse({ phase, prompt, rawResponse, parsed, durationMs: Date.now()-t0 })
      if (parsed) return parsed
      lastErr = 'JSON parse'
    } catch(e) { lastErr = e.message }
  }
  return null // text calls are non-fatal
}

function safeJSON(t) {
  try { return JSON.parse((t||'').replace(/```json\n?/g,'').replace(/```\n?/g,'').trim()) }
  catch { return null }
}

function checkExpired(d) {
  try {
    const p = d.split('/')
    const dt = p.length === 3 ? new Date(`${p[2]}-${p[1].padStart(2,'0')}-${p[0].padStart(2,'0')}`)
             : p.length === 2 ? new Date(`${p[1]}-${p[0].padStart(2,'0')}-01`) : null
    return dt ? dt < new Date() : false
  } catch { return false }
}

function fallbackInfo(type) {
  if (type === 'AYURVEDIC') return { whatItDoes: 'Ayurvedic product.', ayurvedicWarning: 'Regulated by AYUSH Ministry. Consult a qualified practitioner.', commonUses:[], sideEffects:[], importantWarnings:[], prescriptionRequired:false }
  if (type === 'SUPPLEMENT') return { whatItDoes: 'Dietary supplement.', supplementWarning: 'Do not exceed stated dose. Consult doctor if on other medicines.', commonUses:[], sideEffects:[], importantWarnings:[], prescriptionRequired:false }
  return { whatItDoes: 'Medicine information unavailable.', commonUses:[], sideEffects:[], importantWarnings:[], prescriptionRequired:false }
}

// ─── IMAGE COMPRESSION ────────────────────────────────────────────────────────
export async function compressAndEncode(file) {
  return new Promise((resolve, reject) => {
    const img = new Image(), url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      const MAX = 1600
      if (width > MAX || height > MAX) {
        if (width > height) { height = Math.round(height/width*MAX); width = MAX }
        else { width = Math.round(width/height*MAX); height = MAX }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width; canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = '#fff'; ctx.fillRect(0,0,width,height); ctx.drawImage(img,0,0,width,height)
      const tryEncode = (quality, cb) => {
        canvas.toBlob(blob => {
          const r = new FileReader()
          r.onload = () => cb(r.result.split(',')[1])
          r.onerror = reject
          r.readAsDataURL(blob)
        }, 'image/jpeg', quality)
      }
      tryEncode(0.90, b64 => {
        if (b64.length > 4_000_000) tryEncode(0.70, resolve)
        else resolve(b64)
      })
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Could not load image')) }
    img.src = url
  })
}

// ─── PRESCRIPTION SCAN ────────────────────────────────────────────────────────
export const PRESCRIPTION_PROMPT = `Medical prescription reader. Extract ONLY patient name, doctor/hospital name, date, and the list of prescribed medicines.
Strive to read handwriting accurately. Infer common medical abbreviations (e.g., "1-0-1" = Morning & Night, "BD" = twice a day, "PC" = after food, "OD" = once a day).
If the image is totally unreadable or NOT a medical prescription, set cannotRead=true.

JSON only, no markdown:
{
  "doctorName": "Dr. Name / Clinic Name",
  "patientName": "Patient Name",
  "date": "Date if written",
  "medicines": [
    {
      "name": "Full drug name and strength",
      "dosage": "e.g., 1 tablet, 5ml",
      "frequency": "e.g., 1-1-1, or Twice a day",
      "duration": "e.g., 5 days",
      "instructions": "e.g., After food"
    }
  ],
  "confidence": 85,
  "cannotRead": false,
  "cannotReadReason": null
}`

export async function scanPrescription(imageBase64, mimeType = 'image/jpeg') {
  
  const img = await callVision(imageBase64, mimeType, PRESCRIPTION_PROMPT)
  
  if (img.cannotRead) {
    img.cannotReadReason = img.cannotReadReason || 'Could not read the prescription clearly. Try taking a brighter, closer photo.'
  }
  
  return {
    isPrescription: true,
    data: img
  }
}

// ─── PRESCRIPTION MEDICINE LOOKUP (QoL) ──────────────────────────────────────
export async function lookupMedicineNameOnly(name) {
  // Start DB load immediately
  await ensureLoaded()

  // Parse salt composition from name
  const qSalts = parseSalts(name)
  const saltComposition = name // use full name as best effort, or extract names
  
  // Lookup CDSCO and Jan Aushadhi
  const cdscoResult = lookupCDSCO(saltComposition)
  const jaLookup = lookupJanAushadhi(saltComposition, null, null)
  const jaBest = jaLookup.best
  const jaDoseDiff = jaLookup.doseMismatch

  // Call text prompt for description and generics
  let info = null, aiGenerics = []
  try {
    const [infoRes, genRes] = await Promise.allSettled([
      callText(mkDescPrompt(name, saltComposition, 'MEDICINE')),
      callText(mkGenericsPrompt(saltComposition, 'MEDICINE')),
    ])
    info = infoRes.status === 'fulfilled' ? infoRes.value : null
    if (info) info.prescriptionRequired = resolveRx(saltComposition, info.prescriptionRequired)
    if (genRes.status === 'fulfilled' && Array.isArray(genRes.value)) {
      // Extract primary drug names from the query salt for validation
      const queryDrugNames = (saltComposition || '')
        .toLowerCase()
        .split(/\band\b|\+|,/i)
        .map(s => s.replace(/\d+\s*(mg|mcg|g|iu|ml)/gi, '').trim())
        .filter(s => s.length > 3)

      const seen = new Set()
      aiGenerics = genRes.value
        .filter(g => g && g.name && g.brand)
        .filter(g => {
          if (!queryDrugNames.length) return true
          const returnedSalt = (g.salt || '').toLowerCase()
          const returnedName = (g.name || '').toLowerCase()
          return queryDrugNames.every(drug =>
            returnedSalt.includes(drug) || returnedName.includes(drug)
          )
        })
        .filter(g => {
          const key = (g.brand || '').toLowerCase()
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        .slice(0, 3)
    }
  } catch (e) {
    console.error(e)
  }

  let allAlts = [
    ...(jaBest ? [jaBest] : []),
    ...aiGenerics,
  ]

  // Enriched with live prices if possible
  if (allAlts.length > 0) {
    try {
      const davaMap = await batchFetchDavaIndiaPrices(allAlts)
      allAlts = allAlts.map(alt => {
        const key = alt.salt || alt.name
        const dava = davaMap.get(key)
        if (!dava) return alt
        return {
          ...alt,
          mrp: dava.mrp,
          estimatedMrp: dava.mrp,
          packSize: dava.packSize || alt.packSize,
          perUnit: dava.perUnit ?? alt.perUnit,
          priceSource: 'DavaIndia',
          highConfidence: true,
          aiEstimated: false,
          davaIndiaName: dava.name,
        }
      })
    } catch {}
  }

  const authenticity = {
    status: 'CANNOT_DETERMINE',
    reason: 'Prescription lookup — no visual package present.',
    genuineSignalsFound: [],
    fakeSignalsFound: [],
    cdscoBadge: cdscoResult.badge || 'Salt not found in CDSCO registry.',
    cdscoIndication: cdscoResult.indication || null,
    cdscoFound: cdscoResult.found,
    approvalDate: cdscoResult.approvalDate || null,
    warning: null,
  }

  return {
    productType: 'MEDICINE',
    brandName: name,
    saltComposition: saltComposition,
    manufacturer: null,
    mrp: null,
    unitSize: null,
    batchNumber: null,
    expiryDate: null,
    isExpired: false,
    licenceNumber: null,
    confidence: 95,
    saltSource: 'PRESCRIPTION',
    doseUnconfirmed: false,
    cannotRead: false,
    cannotReadReason: null,
    authenticity,
    medicineInfo: info || fallbackInfo('MEDICINE'),
    alternatives: {
      hasGenerics: allAlts.length > 0,
      janAushadhiAvailable: !!jaBest,
      topAlternatives: allAlts,
      doseMismatchAlt: jaDoseDiff,
      jaCount: jaBest ? 1 : 0,
      savingsSummary: buildSavingsSummary(jaBest, null, null),
      pharmacyLinks: pharmacyLinks(saltComposition),
      whereToFind: 'Jan Aushadhi Kendras — janaushadhi.gov.in · 1800-180-8080',
      disclaimer: 'Jan Aushadhi prices from official BPPI database. HIGH CONFIDENCE prices are sourced live from DavaIndia. AI ESTIMATED prices are approximate.',
    },
    dataSource: {
      salt: 'Prescription lookup',
      alts: 'BPPI Jan Aushadhi DB + AI',
      cdsco: cdscoResult.found ? 'CDSCO Drug Registry' : 'Not in CDSCO registry',
      cdscoFound: cdscoResult.found,
    }
  }
}


