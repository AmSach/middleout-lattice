import React, { useState } from 'react'

const JA_STORE_URL = 'https://janaushadhi.gov.in/near-by-kendra'
const REPORT_FORM_URL = 'https://docs.google.com/forms/d/e/1FAIpQLSce6duzii7D1SlYOYI3DG45mVEJUyl3wSzByoYSvyHNStqFGA/viewform'

// ─── Translation helper for AI-generated text ────────────────────────────────
// Sends AI-generated strings through /api/groq proxy (keys stay server-side)
async function translateTexts(texts, targetLang) {
  if (targetLang === 'en' || !texts || texts.length === 0) return texts
  const langNames = { hi: 'Hindi', bn: 'Bengali', te: 'Telugu', mr: 'Marathi', ta: 'Tamil', gu: 'Gujarati' }
  const langName = langNames[targetLang] || 'Hindi'
  try {
    const res = await fetch('/api/groq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        max_tokens: 1500,
        temperature: 0.1,
        messages: [{ role: 'user', content: `Translate each item in this JSON array to ${langName}. Keep medical/drug names and numbers in English. Return ONLY the JSON array, no markdown.\n\n${JSON.stringify(texts)}` }]
      })
    })
    const data = await res.json()
    const raw = data?.choices?.[0]?.message?.content || ''
    const cleaned = raw.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim()
    const parsed = JSON.parse(cleaned)
    return Array.isArray(parsed) ? parsed : texts
  } catch { return texts }
}

export default function ResultsPanel({ results, preview, onReset, t, lang }) {
  const [card, setCard] = useState(0)
  const [reported, setReported] = useState(false)
  const [translated, setTranslated] = useState(null)
  const [translating, setTranslating] = useState(false)

  const [isBookmarked, setIsBookmarked] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('agada_bookmarks') || '[]')
      return saved.some(b => b.brandName === results.brandName && b.saltComposition === results.saltComposition)
    } catch {
      return false
    }
  })

  const toggleBookmark = () => {
    try {
      const saved = JSON.parse(localStorage.getItem('agada_bookmarks') || '[]')
      let updated
      if (isBookmarked) {
        updated = saved.filter(b => !(b.brandName === results.brandName && b.saltComposition === results.saltComposition))
        setIsBookmarked(false)
      } else {
        updated = [...saved, {
          brandName: results.brandName,
          saltComposition: results.saltComposition,
          timestamp: Date.now(),
          results: results
        }]
        setIsBookmarked(true)
      }
      localStorage.setItem('agada_bookmarks', JSON.stringify(updated))
    } catch (e) {
      console.error(e)
    }
  }


  // Auto-translate AI-generated fields when lang != en
  React.useEffect(() => {
    if (lang === 'en') { setTranslated(null); return }
    const info = results?.medicineInfo
    if (!info) return
    setTranslating(true)
    const toTranslate = [
      info.whatItDoes || '',
      info.howToTake || '',
      info.overdoseRisk || '',
      ...(info.commonUses || []),
      ...(info.sideEffects || []),
      ...(info.importantWarnings || []),
      info.doNotTakeWith || '',
      info.ayurvedicWarning || '',
      info.supplementWarning || '',
    ]
    translateTexts(toTranslate, lang).then(result => {
      let i = 0
      const uses = info.commonUses || []
      const side = info.sideEffects || []
      const warn = info.importantWarnings || []
      setTranslated({
        whatItDoes:        result[i++],
        howToTake:         result[i++],
        overdoseRisk:      result[i++],
        commonUses:        uses.map(() => result[i++]),
        sideEffects:       side.map(() => result[i++]),
        importantWarnings: warn.map(() => result[i++]),
        doNotTakeWith:     result[i++],
        ayurvedicWarning:  result[i++],
        supplementWarning: result[i++],
      })
      setTranslating(false)
    }).catch(() => setTranslating(false))
  }, [lang, results])

  const info = (translated || results?.medicineInfo || {})
  const alts = results?.alternatives || {}
  const auth = results?.authenticity || {}
  const jaAlts    = (alts.topAlternatives || []).filter(a => a.isJanAushadhi)
  const otherAlts = (alts.topAlternatives || []).filter(a => !a.isJanAushadhi)

  // Real savings % — computed from actual DB data, not hardcoded
  const brandedMrp    = results?.mrp ? parseFloat(results.mrp) : null
  const brandedUnitSz = results?.unitSize || null
  const brandedPerUnit = brandedMrp && brandedUnitSz
    ? (() => { const n = brandedUnitSz.match(/(\d+)/); return n ? Math.round(brandedMrp / parseInt(n[1]) * 100) / 100 : brandedMrp / 10 })()
    : brandedMrp ? brandedMrp / 10 : null

  const cheapestAlt = alts.topAlternatives?.[0]
  const savingsPct = (brandedPerUnit && cheapestAlt?.perUnit)
    ? Math.round((1 - cheapestAlt.perUnit / brandedPerUnit) * 100)
    : null
  const isCheapest = !alts.hasGenerics || (brandedPerUnit && cheapestAlt?.perUnit && cheapestAlt.perUnit >= brandedPerUnit)

  // Helper for consistent layout wrapping
  const LayoutWrapper = ({ children }) => (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)', height: '100%', overflow: 'hidden' }}>
      {/* Sticky Header */}
      <div style={{ padding: '14px 16px', background: '#fff', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 10, boxShadow: 'var(--shadow)' }}>
        <button onClick={onReset} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14, fontWeight: 600, color: 'var(--textlt)', padding: '6px 0', border: 'none', background: 'transparent', cursor: 'pointer' }}>
          <span style={{ fontSize: 18, lineHeight: 1 }}>‹</span> Back
        </button>
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--navy)', position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>Scan Results</h2>
        <div style={{ width: 60 }} /> {/* Spacer to balance absolute center */}
      </div>
      
      {/* Scrollable Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 16px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {children}
      </div>

      {/* Sticky Footer */}
      <div style={{ padding: '14px 16px', background: '#fff', borderTop: '1px solid var(--border)', position: 'sticky', bottom: 0, zIndex: 10, boxShadow: '0 -1px 3px rgba(0,0,0,0.04)' }}>
        <button onClick={onReset} style={{ width: '100%', height: 48, background: 'var(--navy)', borderRadius: 12, color: '#fff', fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'background 0.2s', border: 'none', cursor: 'pointer' }}>
          📷 Scan Another Medicine
        </button>
      </div>
    </div>
  )

  // Hard block — not a medicine at all
  // ── Hard block: HAZARDOUS substance — show danger warning ─────────────────
  if (results?.productType === 'HAZARDOUS') {
    return (
      <LayoutWrapper>
        <div style={{ background: '#fff3f3', border: '2.5px solid #e53935', borderRadius: 14, padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, textAlign: 'center', boxShadow: '0 4px 18px rgba(229,57,53,0.15)' }}>
          <span style={{ fontSize: 56 }}>☠️</span>
          <div style={{ fontSize: 18, fontWeight: 800, color: '#b71c1c', letterSpacing: 0.3 }}>⚠️ HAZARDOUS — DO NOT CONSUME</div>
          <div style={{ fontSize: 13.5, color: '#c62828', lineHeight: 1.7, maxWidth: 300, fontWeight: 500 }}>
            This appears to be a <strong>dangerous chemical</strong>, not a medicine.
            Do <strong>not</strong> ingest, inhale, or allow contact with skin or eyes.
          </div>
          {results.brandName && (
            <div style={{ fontSize: 12, color: '#b71c1c', background: '#ffebee', padding: '6px 14px', borderRadius: 8, fontWeight: 600 }}>
              Detected: {results.brandName}
            </div>
          )}
          <div style={{ background: '#ffebee', border: '1.5px solid #ef9a9a', borderRadius: 10, padding: '12px 16px', width: '100%', maxWidth: 300 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#b71c1c', marginBottom: 6 }}>🚨 Emergency / Poison Control</div>
            <div style={{ fontSize: 13, color: '#c62828', fontWeight: 600 }}>India Poison Control: <a href="tel:18001116117" style={{ color: '#b71c1c' }}>1800-116-117</a></div>
            <div style={{ fontSize: 11, color: '#c62828', marginTop: 3 }}>Free · 24×7 · All India</div>
          </div>
          <div style={{ fontSize: 11, color: '#e57373', lineHeight: 1.5 }}>
            In case of accidental ingestion, call Poison Control immediately.<br/>Do not induce vomiting unless instructed by a medical professional.
          </div>
        </div>
      </LayoutWrapper>
    )
  }

  // ── Hard block: not a medicine at all ──────────────────────────────────────
  if (results?.productType === 'NOT_MEDICINE') {
    return (
      <LayoutWrapper>
        <div style={{ background: '#fff', border: '1.5px solid var(--border)', borderRadius: 14, padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, textAlign: 'center', boxShadow: 'var(--shadow)' }}>
          <span style={{ fontSize: 48 }}>🚫</span>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--navy)' }}>Not a medicine</div>
          <div style={{ fontSize: 13.5, color: 'var(--textlt)', lineHeight: 1.6, maxWidth: 280 }}>
            {results.cannotReadReason || 'This does not appear to be a medicine. Agada only works with pharmaceutical products.'}
          </div>
          {results.brandName && (
            <div style={{ fontSize: 12, color: 'var(--textlt)', background: 'var(--bgsoft)', padding: '6px 12px', borderRadius: 8 }}>
              Detected: <strong>{results.brandName}</strong>
            </div>
          )}
        </div>
      </LayoutWrapper>
    )
  }



  return (
    <LayoutWrapper>

      {/* Top banner */}
      <div style={{ background: '#fff', border: '1.5px solid var(--border)', borderRadius: 14, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12, boxShadow: 'var(--shadow)', animation: 'fadeUp 0.3s ease' }}>
        {preview
          ? <img src={preview} alt="" style={{ width: 44, height: 44, borderRadius: 9, objectFit: 'cover', flexShrink: 0, border: '1px solid var(--border)' }} />
          : <div style={{ width: 44, height: 44, borderRadius: 9, background: 'var(--greenlt)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>💊</div>
        }
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--navy)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{results.brandName || 'Medicine'}</div>
          <div style={{ fontSize: 11, color: 'var(--textlt)', marginTop: 1 }}>{results.saltComposition || results.productType}</div>
          <div style={{ display: 'flex', gap: 5, marginTop: 5, flexWrap: 'wrap' }}>
            {results.saltSource === 'QR_BARCODE' && <span style={badge('green')}>✓ QR VERIFIED</span>}
            {results.dataSource?.cdscoFound && <span style={badge('green')}>✓ CDSCO</span>}
            <span style={badge('blue')}>BPPI DB</span>
            {results.batchNumber && <span style={badge('gray')}>Batch: {results.batchNumber}</span>}
            {results.isExpired && <span style={badge('red')}>⚠ EXPIRED</span>}
            {translating && <span style={badge('amber')}>Translating...</span>}
          </div>
        </div>
        
        {/* Bookmark Button */}
        <button
          onClick={toggleBookmark}
          title={isBookmarked ? "Remove Bookmark" : "Bookmark Medicine"}
          style={{
            width: 38,
            height: 38,
            borderRadius: '50%',
            background: isBookmarked ? 'var(--safflt)' : 'var(--bgsoft)',
            border: `1.5px solid ${isBookmarked ? 'var(--saffron)' : 'var(--border)'}`,
            color: isBookmarked ? 'var(--saffron)' : 'var(--textlt)',
            fontSize: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s',
            flexShrink: 0
          }}
        >
          {isBookmarked ? '★' : '☆'}
        </button>

        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--green)', background: 'var(--greenlt)', padding: '3px 9px', borderRadius: 8, flexShrink: 0 }}>
          {results.confidence || 70}%
        </div>
      </div>

      {/* Low confidence warning */}
      {(results.confidence || 70) < 50 && (
        <div style={{ background: '#FFFBEB', border: '1.5px solid #FCD34D', borderRadius: 10, padding: '10px 13px', fontSize: 12.5, color: '#92400E', lineHeight: 1.55 }}>
          ⚠ Low confidence scan — the image may be unclear or partially obscured. Results may be inaccurate. Try scanning in better light.
        </div>
      )}

      {/* Dose unconfirmed warning — salt readable but dose not on front of pack */}
      {results.doseUnconfirmed && (
        <div style={{ background: '#FFFBEB', border: '1.5px solid #FCD34D', borderRadius: 10, padding: '10px 13px', fontSize: 12.5, color: '#92400E', lineHeight: 1.6, display: 'flex', gap: 9, alignItems: 'flex-start' }}>
          <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
          <div>
            <strong>Dose not confirmed</strong> — the dose ({results.saltComposition}) was not visible on this side of the pack. It may be printed on the back or side label.<br />
            <span style={{ fontWeight: 600 }}>Please check the full label before taking this medicine.</span> Alternatives shown are based on salt name only — verify the strength with your pharmacist.
          </div>
        </div>
      )}


      {/* Modern Segmented Control */}
      <div style={{ display: 'flex', background: 'var(--border)', padding: 4, borderRadius: 12, marginBottom: 4, animation: 'fadeUp 0.3s ease 0.1s both' }}>
        {[['🛡️', 'Authentic'], ['💡', 'Usage'], ['💸', 'Alternatives']].map(([icon, label], i) => (
          <button key={i} onClick={() => setCard(i)} style={{ flex: 1, padding: '10px 4px', borderRadius: 9, background: card === i ? '#fff' : 'transparent', color: card === i ? 'var(--navy)' : 'var(--textlt)', fontSize: 13, fontWeight: card === i ? 700 : 500, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, transition: 'all 0.2s', boxShadow: card === i ? '0 2px 8px rgba(0,0,0,0.08)' : 'none', border: 'none' }}>
            <span style={{ fontSize: 18, filter: card === i ? 'none' : 'grayscale(100%)', opacity: card === i ? 1 : 0.6 }}>{icon}</span>{label}
          </button>
        ))}
      </div>

      {/* Cards Display */}
      <div style={{ animation: 'fadeIn 0.2s ease', flex: 1 }}>
        {card === 0 && <AuthCard auth={auth} results={results} t={t} reported={reported} setReported={setReported} />}
        {card === 1 && <InfoCard info={info} results={results} translating={translating} />}
        {card === 2 && <AltCard alts={alts} jaAlts={jaAlts} otherAlts={otherAlts} savingsPct={savingsPct} isCheapest={isCheapest} brandedPerUnit={brandedPerUnit} cheapestAlt={cheapestAlt} />}
      </div>
    </LayoutWrapper>
  )
}

// ─── CARD 1: AUTHENTICITY ────────────────────────────────────────────────────
function AuthCard({ auth, results, t, reported, setReported }) {
  const [expanded, setExpanded] = useState(false)
  const isGenuine = auth.status === 'LIKELY_GENUINE'
  const isFake    = auth.status === 'LIKELY_FAKE'

  const statusConfig = isGenuine ? {
    bg: '#F0FDF4', border: '#86EFAC', iconBg: '#16A34A', icon: '✓', iconColor: '#fff',
    titleColor: '#15803D', title: 'Verification: Genuine', sub: 'Found in official CDSCO registry',
  } : isFake ? {
    bg: 'var(--redlt)', border: '#FECACA', iconBg: 'var(--red)', icon: '✕', iconColor: '#fff',
    titleColor: 'var(--red)', title: 'Verification: Suspicious', sub: 'Potential visual anomalies detected',
  } : {
    bg: '#FFFBEB', border: '#FCD34D', iconBg: 'var(--amber)', icon: '?', iconColor: '#fff',
    titleColor: '#92400E', title: 'Verification: Inconclusive', sub: 'Need more clear visual evidence',
  }

  return (
    <div style={{ background: statusConfig.bg, border: `1.5px solid ${statusConfig.border}`, borderRadius: 14, overflow: 'hidden', animation: 'fadeUp 0.3s ease' }}>

      {/* Status row */}
      <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 13 }}>
        <div style={{ width: 46, height: 46, borderRadius: '50%', background: statusConfig.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: statusConfig.iconColor, fontWeight: 700, flexShrink: 0, animation: 'popIn 0.4s cubic-bezier(0.34,1.56,0.64,1) 0.1s both' }}>{statusConfig.icon}</div>
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, color: statusConfig.titleColor }}>{statusConfig.title}</div>
          <div style={{ fontSize: 12, color: 'var(--textlt)' }}>{statusConfig.sub}</div>
        </div>
      </div>

      <div style={{ background: 'rgba(255,255,255,0.6)', padding: '12px 16px', borderTop: '1px solid rgba(0,0,0,0.06)', display: 'flex', flexDirection: 'column', gap: 8 }}>

        {/* Genuine signals */}
        {auth.genuineSignalsFound?.length > 0 && (
          <div>
            <div style={sectionLabel('green')}>Genuine signals found</div>
            {auth.genuineSignalsFound.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: '#166534', marginBottom: 4, alignItems: 'flex-start' }}>
                <span style={{ color: '#16A34A', fontWeight: 700, flexShrink: 0 }}>✓</span>{s}
              </div>
            ))}
          </div>
        )}

        {/* Fake signals */}
        {auth.fakeSignalsFound?.length > 0 && (
          <div>
            <div style={sectionLabel('red')}>Suspicious signals</div>
            {auth.fakeSignalsFound.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: '#991B1B', marginBottom: 4, alignItems: 'flex-start' }}>
                <span style={{ fontWeight: 700, flexShrink: 0 }}>⚠</span>{s}
              </div>
            ))}
          </div>
        )}

        {/* Fields table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            ['Brand', results.brandName],
            ['Manufacturer', results.manufacturer],
            ['Type', results.productType],
            ['Schedule', results.medicineInfo?.prescriptionRequired ? 'Prescription (Rx)' : 'OTC — no prescription'],
            ['Expiry', results.expiryDate],
            ['Licence No.', results.licenceNumber],
          ].filter(([,v]) => v).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 10px', background: 'rgba(255,255,255,0.7)', borderRadius: 8, border: '1px solid rgba(0,0,0,0.05)' }}>
              <span style={{ fontSize: 11, color: 'var(--textlt)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k}</span>
              <span style={{ fontSize: 12.5, color: 'var(--textmd)', fontWeight: 500, maxWidth: '60%', textAlign: 'right' }}>{v}</span>
            </div>
          ))}
        </div>

        {/* CDSCO fact — clean, no conflicting drug name */}
        {auth.cdscoBadge && (
          <div style={{ padding: '10px 13px', background: auth.cdscoFound ? '#F0FDF4' : 'var(--bgsoft)', border: `1px solid ${auth.cdscoFound ? '#86EFAC' : 'var(--border)'}`, borderRadius: 9 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: auth.cdscoFound ? '#15803D' : 'var(--textlt)', marginBottom: auth.cdscoIndication ? 4 : 0 }}>
              {auth.cdscoBadge}
            </div>
            {auth.cdscoIndication && (
              <div style={{ fontSize: 12, color: 'var(--textmd)', lineHeight: 1.5 }}>
                Approved use: {auth.cdscoIndication}
              </div>
            )}
            {auth.approvalDate && (
              <div style={{ fontSize: 11, color: 'var(--textlt)', marginTop: 3 }}>Since: {auth.approvalDate}</div>
            )}
          </div>
        )}

        {/* Expired */}
        {results.isExpired && (
          <div style={{ padding: '10px 12px', background: 'var(--redlt)', border: '1px solid #FECACA', borderRadius: 9, fontSize: 12.5, color: '#991B1B', lineHeight: 1.55 }}>
            ⚠ This medicine appears to be <strong>expired</strong>. Do not consume. Return to your chemist.
          </div>
        )}

        {/* Fake action */}
        {isFake && (
          <div style={{ padding: '10px 12px', background: 'var(--redlt)', border: '1px solid #FECACA', borderRadius: 9, fontSize: 12.5, color: '#991B1B', lineHeight: 1.55 }}>
            Do not consume. Return to chemist and ask for CDSCO licence proof.<br />Report to CDSCO: <strong>1800-180-3024</strong> (free)
          </div>
        )}
      </div>

      {/* Report button */}
      <div style={{ padding: '10px 16px', borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <button onClick={() => { window.open(REPORT_FORM_URL, '_blank'); setReported(true) }} style={{ width: '100%', padding: '10px', borderRadius: 10, background: reported ? 'var(--greenlt)' : 'var(--redlt)', border: `1.5px solid ${reported ? '#86EFAC' : '#FECACA'}`, fontSize: 12.5, fontWeight: 600, color: reported ? '#15803D' : 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          {reported ? '✓ Report submitted. Thank you.' : '🚨 Report this as a fake'}
        </button>
      </div>
    </div>
  )
}

// ─── CARD 2: MEDICINE INFO ────────────────────────────────────────────────────
function InfoCard({ info, results, translating }) {
  const [showSide, setShowSide] = useState(false)
  const isAyurvedic   = results.productType === 'AYURVEDIC'
  const isSupplement  = results.productType === 'SUPPLEMENT'

  return (
    <div style={{ background: '#fff', border: '1.5px solid var(--border)', borderRadius: 14, overflow: 'hidden', animation: 'fadeUp 0.3s ease' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--navy)', display: 'flex', alignItems: 'center', gap: 8 }}>💡 Usage & Safety</div>
        {translating && <span style={badge('amber')}>Translating...</span>}
      </div>
      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>

        <p style={{ fontSize: 13.5, color: 'var(--textmd)', lineHeight: 1.7, margin: 0 }}>{info.whatItDoes}</p>

        {info.howToTake && (
          <div style={{ padding: '10px 13px', background: 'var(--greenlt)', border: '1.5px solid #A7D9CA', borderRadius: 10 }}>
            <div style={sectionLabel('green')}>How to take</div>
            <p style={{ fontSize: 13, color: '#166534', lineHeight: 1.6, margin: 0 }}>{info.howToTake}</p>
          </div>
        )}

        {info.commonUses?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {info.commonUses.map((u, i) => (
              <span key={i} style={{ fontSize: 11.5, background: '#F0F9FF', color: '#0369A1', borderRadius: 20, padding: '3px 11px', border: '1px solid #BAE6FD' }}>{u}</span>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bgsoft)', borderRadius: 9, border: '1px solid var(--border)' }}>
          <span style={{ fontSize: 13, color: 'var(--textmd)' }}>Prescription required?</span>
          <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 6, background: info.prescriptionRequired ? 'var(--redlt)' : 'var(--greenlt)', color: info.prescriptionRequired ? 'var(--red)' : 'var(--greendk)', letterSpacing: '0.04em' }}>
            {info.prescriptionRequired ? 'YES — Rx' : 'NO — OTC'}
          </span>
        </div>

        {info.importantWarnings?.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {info.importantWarnings.map((w, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '9px 12px', background: '#FEF3C7', borderRadius: 10, borderLeft: '3px solid var(--amber)', alignItems: 'flex-start' }}>
                <span style={{ flexShrink: 0 }}>⚠️</span>
                <span style={{ fontSize: 12.5, color: '#78350F', lineHeight: 1.5 }}>{w}</span>
              </div>
            ))}
          </div>
        )}

        {info.sideEffects?.length > 0 && (
          <>
            <button onClick={() => setShowSide(s => !s)} style={{ fontSize: 12.5, color: 'var(--green)', fontWeight: 600, textAlign: 'left', display: 'flex', gap: 6, alignItems: 'center' }}>
              <span>{showSide ? '▲' : '▼'}</span> Side effects ({info.sideEffects.length})
            </button>
            {showSide && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {info.sideEffects.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, padding: '7px 11px', background: 'var(--bgsoft)', borderRadius: 8, fontSize: 13, color: 'var(--textmd)', alignItems: 'center' }}>
                    <span style={{ color: 'var(--amber)', fontSize: 9 }}>●</span>{s}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {info.overdoseRisk && (
          <div style={{ padding: '9px 12px', background: 'var(--redlt)', borderRadius: 9, border: '1px solid #FECACA' }}>
            <div style={sectionLabel('red')}>⚠ Overdose risk</div>
            <p style={{ fontSize: 12.5, color: '#7F1D1D', lineHeight: 1.55, margin: 0 }}>{info.overdoseRisk}</p>
          </div>
        )}

        {isAyurvedic && info.ayurvedicWarning && (
          <div style={{ padding: '10px 12px', background: 'var(--greenlt)', border: '1.5px solid #A7D9CA', borderRadius: 10, fontSize: 12.5, color: '#166534', lineHeight: 1.6 }}>
            🌿 {info.ayurvedicWarning}
          </div>
        )}

        {isSupplement && info.supplementWarning && (
          <div style={{ padding: '10px 12px', background: '#FFFBEB', border: '1.5px solid #FCD34D', borderRadius: 10, fontSize: 12.5, color: '#78350F', lineHeight: 1.6 }}>
            💊 {info.supplementWarning}
          </div>
        )}

        {info.doNotTakeWith && (
          <div style={{ padding: '9px 12px', background: 'var(--redlt)', borderRadius: 9, fontSize: 12.5, color: '#7F1D1D', lineHeight: 1.5 }}>
            <strong>🚫 Do not take with: </strong>{info.doNotTakeWith}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── CARD 3: ALTERNATIVES ─────────────────────────────────────────────────────
function AltCard({ alts, jaAlts, otherAlts, savingsPct, isCheapest, brandedPerUnit, cheapestAlt }) {
  const aiAlts = (alts.topAlternatives || []).filter(a => a.aiEstimated)
  
  // Savings Calculator state (QoL 1)
  const [calcDays, setCalcDays] = useState(30)
  const [calcQty, setCalcQty] = useState(1)

  const showCalc = !isCheapest && cheapestAlt && brandedPerUnit && cheapestAlt.perUnit < brandedPerUnit

  const totalQty = calcDays * calcQty
  const brandedTotal = Math.round(totalQty * brandedPerUnit)
  const genericTotal = Math.round(totalQty * cheapestAlt?.perUnit)
  const savedAmount = brandedTotal - genericTotal

  return (
    <div style={{ background: '#fff', border: '1.5px solid var(--border)', borderRadius: 14, overflow: 'hidden', animation: 'fadeUp 0.3s ease' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--navy)' }}>💸 Cheaper alternatives</div>
        <span style={badge('green')}>BPPI + AI</span>
      </div>

      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Cheapest message OR savings hero */}
        {isCheapest ? (
          <div style={{ padding: '13px 15px', background: 'var(--greenlt)', border: '1.5px solid #A7D9CA', borderRadius: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 30 }}>🏆</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--greendk)', marginBottom: 2 }}>This is already the cheapest available</div>
              <div style={{ fontSize: 12, color: '#166534', lineHeight: 1.5 }}>No cheaper Jan Aushadhi generic found. You're already paying a fair price.</div>
            </div>
          </div>
        ) : savingsPct && savingsPct > 0 ? (
          <div style={{ padding: '13px 15px', background: 'var(--greenlt)', border: '1.5px solid #A7D9CA', borderRadius: 12, display: 'flex', gap: 14, alignItems: 'center' }}>
            <div style={{ fontWeight: 800, fontSize: 38, color: 'var(--green)', lineHeight: 1, flexShrink: 0 }}>{savingsPct}%</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--greendk)', marginBottom: 3 }}>Savings available</div>
              <div style={{ fontSize: 12, color: '#166534', lineHeight: 1.5 }}>{alts.savingsSummary}</div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '12px 14px', background: 'var(--bgsoft)', borderRadius: 10, fontSize: 13, color: 'var(--textlt)' }}>
            {alts.savingsSummary || 'Cheaper alternatives listed below.'}
          </div>
        )}

        {/* Savings Calculator Widget (QoL 1) */}
        {showCalc && (
          <div style={{
            background: 'var(--bgsoft)',
            border: '1.5px solid var(--border)',
            borderRadius: 12,
            padding: '14px',
            marginTop: 4,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.02)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--navy)' }}>🧮 Savings Calculator</span>
              <span style={{ fontSize: 11, fontWeight: 600, background: 'var(--greenlt)', color: 'var(--green)', padding: '2px 8px', borderRadius: 20 }}>
                Interactive
              </span>
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between' }}>
              {/* Daily Dosage */}
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 10.5, color: 'var(--textlt)', fontWeight: 600, display: 'block', marginBottom: 5, textTransform: 'uppercase' }}>Tablets / day</label>
                <div style={{ display: 'flex', background: '#fff', borderRadius: 8, border: '1px solid var(--border)', padding: 2 }}>
                  {[1, 2, 3].map(q => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setCalcQty(q)}
                      style={{
                        flex: 1,
                        padding: '6px 0',
                        borderRadius: 6,
                        background: calcQty === q ? 'var(--navy)' : 'transparent',
                        color: calcQty === q ? '#fff' : 'var(--textmd)',
                        fontSize: 12,
                        fontWeight: 700,
                        border: 'none',
                        transition: 'all 0.2s'
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Prescription Days */}
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 10.5, color: 'var(--textlt)', fontWeight: 600, display: 'block', marginBottom: 5, textTransform: 'uppercase' }}>Duration (Days)</label>
                <div style={{ display: 'flex', background: '#fff', borderRadius: 8, border: '1px solid var(--border)', padding: 2 }}>
                  {[10, 30, 90].map(d => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setCalcDays(d)}
                      style={{
                        flex: 1,
                        padding: '6px 0',
                        borderRadius: 6,
                        background: calcDays === d ? 'var(--navy)' : 'transparent',
                        color: calcDays === d ? '#fff' : 'var(--textmd)',
                        fontSize: 12,
                        fontWeight: 700,
                        border: 'none',
                        transition: 'all 0.2s'
                      }}
                    >
                      {d}d
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Custom inputs / sliders for more precision */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--textlt)' }}>
                <span>Custom Duration: {calcDays} Days</span>
              </div>
              <input
                type="range"
                min="5"
                max="180"
                step="5"
                value={calcDays}
                onChange={(e) => setCalcDays(parseInt(e.target.value))}
                style={{
                  width: '100%',
                  height: 4,
                  accentColor: 'var(--green)',
                  background: 'var(--border)',
                  outline: 'none',
                  borderRadius: 2,
                  cursor: 'pointer'
                }}
              />
            </div>

            {/* Visual Bar Comparison Chart */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
              {/* Branded Bar */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--textmd)', marginBottom: 3 }}>
                  <span>Branded Cost</span>
                  <span style={{ fontWeight: 700 }}>₹{brandedTotal}</span>
                </div>
                <div style={{ width: '100%', height: 8, background: '#fff', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
                  <div style={{ width: '100%', height: '100%', background: 'var(--navy)', borderRadius: 4 }} />
                </div>
              </div>

              {/* Generic Bar */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--textmd)', marginBottom: 3 }}>
                  <span>Generic/Alternative Cost</span>
                  <span style={{ fontWeight: 700 }}>₹{genericTotal}</span>
                </div>
                <div style={{ width: '100%', height: 8, background: '#fff', borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border)' }}>
                  <div style={{ width: `${Math.max(5, Math.min(100, (genericTotal / brandedTotal) * 100))}%`, height: '100%', background: 'var(--green)', borderRadius: 4, transition: 'width 0.3s ease' }} />
                </div>
              </div>
            </div>

            {/* Savings Result */}
            <div style={{
              background: '#DCFCE7',
              border: '1px solid #86EFAC',
              borderRadius: 8,
              padding: '10px 12px',
              textAlign: 'center',
              color: '#15803D',
              fontSize: 13,
              fontWeight: 700,
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              marginTop: 4
            }}>
              <span>💰 Save ₹{savedAmount}!</span>
              <span style={{ fontSize: 11, fontWeight: 500, color: '#166534' }}>
                ({savingsPct}% cheaper over {calcDays} days of treatment)
              </span>
            </div>
          </div>
        )}


        {/* Ask your chemist callout */}
        {alts.topAlternatives?.length > 0 && (
          <div style={{ padding: '10px 13px', background: '#EFF6FF', border: '1.5px solid #BFDBFE', borderRadius: 10, fontSize: 12.5, color: '#1E40AF', lineHeight: 1.6 }}>
            💬 <strong>At any chemist, say:</strong> "Do you have a cheaper version of {alts.topAlternatives[0]?.salt?.split(' ')[0] || 'this medicine'}?" — any brand with the same salt is legally equivalent.
          </div>
        )}

        {/* Jan Aushadhi */}
        {jaAlts.length > 0 && (
          <div>
            <div style={{ ...sectionLabel('green'), display: 'flex', alignItems: 'center', gap: 6 }}>
              🏛 Tier 1 — Jan Aushadhi <span style={badge('green')}>VERIFIED PRICE</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--textlt)', marginBottom: 8, marginTop: -4 }}>Govt stores · Cheapest option · ~14,000 locations</div>
            {jaAlts.map((med, i) => <AltRow key={i} med={med} highlight />)}
          </div>
        )}

        {/* Branded generics at any chemist */}
        {otherAlts.length > 0 && (
          <div>
            <div style={{ ...sectionLabel('blue'), display: 'flex', alignItems: 'center', gap: 6 }}>
              🏪 Tier 2 — Any chemist
              <span style={badgeHighConf()}>✓ DAVAINDIA</span>
              <span style={badge('blue')}>AI EST.</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--textlt)', marginBottom: 8, marginTop: -4 }}>
              Same molecule · 1mg prices where available · Others AI-estimated
            </div>
            {otherAlts.map((med, i) => <AltRow key={i} med={med} />)}
          </div>
        )}

        {/* Dose-mismatch alternatives — shown separately with explicit warning */}
        {alts.doseMismatchAlt && (
          <div>
            <div style={{ padding: '9px 13px', background: '#FFFBEB', border: '1.5px solid #FCD34D', borderRadius: 10, marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#92400E', marginBottom: 2 }}>⚠ Different dose — ask your doctor first</div>
              <div style={{ fontSize: 11.5, color: '#78350F', lineHeight: 1.5 }}>These contain the same active salt but at a different strength. Do not substitute without a doctor's advice.</div>
            </div>
            <AltRow med={alts.doseMismatchAlt} dimmed />
          </div>
        )}

        {!alts.hasGenerics && !isCheapest && (
          <div style={{ padding: '10px 12px', background: 'var(--bgsoft)', borderRadius: 9, fontSize: 13, color: 'var(--textlt)', lineHeight: 1.5 }}>
            No cheaper alternatives found. Ask your doctor if a generic is available for this medicine.
          </div>
        )}

        {/* Find Jan Aushadhi store */}
        <a href={JA_STORE_URL} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '12px 14px', background: 'var(--greenlt)', border: '1.5px solid #A7D9CA', borderRadius: 12, textDecoration: 'none' }}>
          <span style={{ fontSize: 20 }}>📍</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--greendk)' }}>Find Jan Aushadhi near me</div>
            <div style={{ fontSize: 11, color: '#166534' }}>janaushadhi.gov.in · 1800-180-8080 (free)</div>
          </div>
          <span style={{ marginLeft: 'auto', color: 'var(--green)', fontSize: 16 }}>›</span>
        </a>

        {/* Live prices on pharmacy sites */}
        {alts.pharmacyLinks?.length > 0 && (
          <div>
            <div style={sectionLabel('gray')}>🔍 Check live prices</div>
            <div style={{ fontSize: 11.5, color: 'var(--textlt)', marginBottom: 8, marginTop: -4 }}>Opens pharmacy site with real-time prices for this salt</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {alts.pharmacyLinks.map(link => (
                <a key={link.name} href={link.url} target="_blank" rel="noopener noreferrer"
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', background: '#fff', border: '1.5px solid var(--border)', borderRadius: 10, textDecoration: 'none', color: 'var(--navy)' }}>
                  <span style={{ fontSize: 16 }}>{link.logo}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{link.name}</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--textlt)', fontSize: 12 }}>›</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Disclaimer */}
        <div style={{ padding: '9px 12px', background: 'var(--bgsoft)', borderRadius: 9, fontSize: 11.5, color: 'var(--textlt)', lineHeight: 1.6, border: '1px solid var(--border)' }}>
          ⚠ Jan Aushadhi prices from BPPI database. <strong>HIGH CONFIDENCE</strong> prices are sourced live from 1mg. <strong>AI EST.</strong> prices are approximate — always verify at the chemist counter. Only buy from licensed pharmacies.
        </div>
      </div>
    </div>
  )
}

function AltRow({ med, highlight, dimmed }) {
  const displayMrp   = med.mrp || med.estimatedMrp
  const isDavaIndia  = med.priceSource === "DavaIndia" || med.priceSource === "1mg" || med.highConfidence === true
  const isJA         = med.isJanAushadhi
  // per-unit label: use perUnitLabel if set, else infer from packSize/unitSize, else 'tablet'
  const unitLabel    = med.perUnitLabel || inferUnitLabel(med.unitSize || med.packSize)

  const bgColor     = (highlight || isJA) ? 'var(--greenlt)'
                    : isDavaIndia          ? '#EBF9F6'
                    : med.aiEstimated      ? '#F0F9FF'
                    : 'var(--bgsoft)'
  const borderColor = (highlight || isJA) ? '#A7D9CA'
                    : isDavaIndia          ? '#5EEAD4'
                    : med.aiEstimated      ? '#BFDBFE'
                    : 'var(--border)'

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '10px 12px', opacity: dimmed ? 0.7 : 1,
      background: bgColor, borderRadius: 10, marginBottom: 7,
      border: `1.5px solid ${borderColor}` }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap', marginBottom: 3 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)' }}>{med.name}</span>
          {isJA        && <span style={badge('green')}>JAN AUSHADHI</span>}
          {isDavaIndia && !isJA && <span style={badgeHighConf()}>✓ HIGH CONFIDENCE</span>}
          {!isDavaIndia && !isJA && med.aiEstimated && <span style={badge('blue')}>AI EST.</span>}
        </div>
        <div style={{ fontSize: 11, color: 'var(--textlt)', lineHeight: 1.5 }}>
          {med.brand && med.brand !== 'BPPI' && <span>{med.brand} · </span>}
          {med.unitSize || med.packSize || ''}
        </div>
        {isDavaIndia && !isJA && (
          <div style={{ fontSize: 10.5, color: '#0D9488', fontWeight: 600, marginTop: 2 }}>📦 Live price · 1mg</div>
        )}
        {!isDavaIndia && med.aiEstimated && (
          <div style={{ fontSize: 10.5, color: '#9CA3AF', marginTop: 2 }}>⚠ AI-estimated — may vary</div>
        )}
        {med.availableAt && !isDavaIndia && (
          <div style={{ fontSize: 10.5, color: 'var(--green)', fontWeight: 600, marginTop: 2 }}>📍 {med.availableAt}</div>
        )}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 10 }}>
        {displayMrp && <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--navy)' }}>₹{displayMrp}</div>}
        {med.perUnit != null && (
          <div style={{ fontSize: 10.5, color: 'var(--textlt)' }}>₹{med.perUnit}/{unitLabel}</div>
        )}
        {med.savings && med.savings !== 'Jan Aushadhi price' && (
          <div style={{ fontSize: 11, color: med.savings.includes('pricier') ? 'var(--amber)' : 'var(--green)', fontWeight: 600 }}>{med.savings}</div>
        )}
        {med.savingsNote && <div style={{ fontSize: 10.5, color: 'var(--textlt)', marginTop: 1 }}>{med.savingsNote}</div>}
      </div>
    </div>
  )
}

// ─── HELPERS ────────────────────────────────────────────────────────────────

// Infer a readable unit label from pack description (e.g. "10 capsules" → "capsule")
function inferUnitLabel(packStr) {
  if (!packStr) return 'tablet'
  const s = packStr.toLowerCase()
  if (/capsule/.test(s)) return 'capsule'
  if (/sachet/.test(s))  return 'sachet'
  if (/patch/.test(s))   return 'patch'
  if (/vial|ampoule/.test(s)) return 'vial'
  if (/ml|gm|g\b/.test(s))   return null   // non-countable — skip per-unit display
  return 'tablet'
}

function badge(color) {
  const configs = {
    green: { bg: '#DCFCE7', color: '#166534' },
    blue:  { bg: '#DBEAFE', color: '#1E40AF' },
    gray:  { bg: '#F3F4F6', color: '#6B7280' },
    red:   { bg: '#FEE2E2', color: '#991B1B' },
    amber: { bg: '#FEF3C7', color: '#92400E' },
  }
  const cfg = configs[color] || configs.gray
  return { fontSize: 9.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: cfg.bg, color: cfg.color, letterSpacing: '0.04em', display: 'inline-block' }
}

function badgeHighConf() {
  return { fontSize: 9.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: '#CCFBF1', color: '#0F766E', letterSpacing: '0.04em', display: 'inline-block' }
}

function sectionLabel(color) {
  const colors = { green: '#166534', red: '#991B1B', gray: '#6B7280', blue: '#1E40AF' }
  return { fontSize: 10.5, fontWeight: 700, color: colors[color] || '#6B7280', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 7, display: 'block' }
}
