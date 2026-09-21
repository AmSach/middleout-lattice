import React, { useState, useRef, useCallback } from 'react'
import { scanMedicine, scanPrescription, compressAndEncode } from '../services/geminiService.js'
import { readBarcode } from '../services/barcodeService.js'
import ResultsPanel from '../components/ResultsPanel.jsx'
import PrescriptionResultsPanel from '../components/PrescriptionResultsPanel.jsx'
import HamMenu from '../components/HamMenu.jsx'
import { useLang, useSetPage } from '../App.jsx'
import { useT } from '../i18n/translations.js'

const VIEWS = { HOME: 'home', LOADING: 'loading', RESULTS: 'results', ERROR: 'error' }

export default function Scanner() {
  const { lang, setLang } = useLang()
  const t = useT(lang)
  const setPage = useSetPage()
  const [view, setView]           = useState(VIEWS.HOME)
  const [results, setResults]     = useState(null)
  const [error, setError]         = useState(null)
  const [preview, setPreview]     = useState(null)
  const [step, setStep]           = useState(0)
  const [barcodeHit, setBarcodeHit] = useState(false)
  const [hamOpen, setHamOpen]     = useState(false)
  const [scanMode, setScanMode]   = useState('medicine')
  const cameraRef = useRef(null)
  const uploadRef = useRef(null)

  // Bookmarks state & synchronizer (QoL 3)
  const [bookmarks, setBookmarks] = useState([])
  React.useEffect(() => {
    if (view === VIEWS.HOME) {
      try {
        const saved = JSON.parse(localStorage.getItem('agada_bookmarks') || '[]')
        saved.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
        setBookmarks(saved)
      } catch (e) {
        console.error(e)
      }
    }
  }, [view])

  const handleSelectBookmark = (bookmark) => {
    setResults(bookmark.results)
    setView(VIEWS.RESULTS)
  }

  const handleDeleteBookmark = (e, bookmark) => {
    e.stopPropagation()
    try {
      const saved = JSON.parse(localStorage.getItem('agada_bookmarks') || '[]')
      const updated = saved.filter(b => !(b.brandName === bookmark.brandName && b.saltComposition === bookmark.saltComposition))
      localStorage.setItem('agada_bookmarks', JSON.stringify(updated))
      setBookmarks(updated)
    } catch (err) {
      console.error(err)
    }
  }


  const handleFile = useCallback(async (file) => {
    if (!file || !file.type.startsWith('image/')) return
    if (file.size > 30 * 1024 * 1024) { alert('Image too large (max 30MB).'); return }
    setView(VIEWS.LOADING); setError(null); setStep(1); setBarcodeHit(false)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(URL.createObjectURL(file))
    try {
      const barcodePromise = scanMode === 'medicine' ? readBarcode(file).catch(() => null) : Promise.resolve(null)
      setStep(1)
      await new Promise(r => setTimeout(r, 400))
      const b64 = await compressAndEncode(file)
      setStep(2)
      
      let res;
      if (scanMode === 'prescription') {
        await new Promise(r => setTimeout(r, 600))
        res = await scanPrescription(b64, 'image/jpeg')
        setStep(3)
        await new Promise(r => setTimeout(r, 300))
        if (res.data.cannotRead) throw new Error(res.data.cannotReadReason || 'Could not read the prescription.')
      } else {
        const barcodeData = await barcodePromise
        if (barcodeData) setBarcodeHit(true)
        await new Promise(r => setTimeout(r, 300))
        res = await scanMedicine(b64, 'image/jpeg', barcodeData)
        setStep(3)
        await new Promise(r => setTimeout(r, 300))
        if (res.cannotRead) throw new Error(res.cannotReadReason || 'Could not read the medicine. Try a clearer photo.')
      }
      
      setResults(res); setView(VIEWS.RESULTS)
    } catch (err) {
      setError(err.message); setView(VIEWS.ERROR)
    }
  }, [preview, scanMode])

  const handleChange = useCallback((e) => {
    const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ''
  }, [handleFile])

  const reset = useCallback(() => {
    setView(VIEWS.HOME); setResults(null); setError(null); setStep(0)
    if (preview) { URL.revokeObjectURL(preview); setPreview(null) }
  }, [preview])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', maxWidth: 540, margin: '0 auto' }}>

      {/* Header */}
      <header style={{ background: 'var(--navy)', padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, background: 'var(--green)', borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#fff', fontSize: 15 }}>अ</div>
          <div>
            <div style={{ color: '#fff', fontWeight: 800, fontSize: 17, lineHeight: 1.1 }}>Agada</div>
            <div style={{ color: '#9CA3AF', fontSize: 10.5 }}>Know Your Medicine</div>
          </div>
        </div>
        <button onClick={() => setHamOpen(o => !o)} style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4.5 }}>
          {[0,1,2].map(i => <span key={i} style={{ width: 17, height: 1.5, background: hamOpen && i===1 ? 'transparent' : '#fff', borderRadius: 1, display: 'block',
            transform: hamOpen ? (i===0 ? 'translateY(6px) rotate(45deg)' : i===2 ? 'translateY(-6px) rotate(-45deg)' : 'none') : 'none', transition: 'all 0.25s' }} />)}
        </button>
      </header>

      <HamMenu open={hamOpen} onClose={() => setHamOpen(false)} lang={lang} setLang={setLang} t={t} onScan={() => { setHamOpen(false); if (view !== VIEWS.HOME) reset() }} />

      {/* Beta banner */}
      <div style={{ background: '#FEF3C7', borderBottom: '1px solid #FCD34D', padding: '7px 16px', textAlign: 'center' }}>
        <span style={{ fontSize: 11.5, color: '#92400E' }}>🚧 <strong>Beta</strong> — {t.betaBanner || 'AI results may not be 100% accurate. Verify with your pharmacist.'}</span>
      </div>

      {view === VIEWS.HOME    && (
        <HomeView
          t={t}
          setPage={setPage}
          bookmarks={bookmarks}
          handleSelectBookmark={handleSelectBookmark}
          handleDeleteBookmark={handleDeleteBookmark}
          onCamera={(mode) => { setScanMode(mode); cameraRef.current?.click() }}
          onUpload={(mode) => { setScanMode(mode); uploadRef.current?.click() }}
        />
      )}
      {view === VIEWS.LOADING && <LoadingView t={t} step={step} preview={preview} barcodeHit={barcodeHit} />}
      {view === VIEWS.RESULTS && (results?.isPrescription ? <PrescriptionResultsPanel results={results} preview={preview} onReset={reset} t={t} lang={lang} /> : <ResultsPanel results={results} preview={preview} onReset={reset} t={t} lang={lang} />)}
      {view === VIEWS.ERROR   && <ErrorView error={error} onReset={reset} t={t} />}

      <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleChange} style={{ display: 'none' }} />
      <input ref={uploadRef} type="file" accept="image/*" onChange={handleChange} style={{ display: 'none' }} />
    </div>
  )
}

function HomeView({ t, setPage, bookmarks, handleSelectBookmark, handleDeleteBookmark, onCamera, onUpload }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'linear-gradient(180deg, var(--bg) 0%, #FFFFFF 100%)', padding: '0 18px 32px', animation: 'fadeIn 0.4s ease' }}>

      {/* Modern Hero Section */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: '40px 0 32px', animation: 'fadeUp 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) both' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--greenlt)', color: 'var(--greendk)', padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 20, boxShadow: '0 2px 8px rgba(15,122,90,0.1)' }}>
          <span style={{ fontSize: 14 }}>✨</span> {t.knowYourMedicine || 'Know Your Medicine'}
        </div>

        <h1 style={{ fontSize: 36, fontWeight: 800, color: 'var(--navy)', lineHeight: 1.15, marginBottom: 14, letterSpacing: '-0.02em' }}>
          {t.heroLine1 || 'Verify.'}<br />
          <span style={{ background: 'linear-gradient(90deg, var(--green), #0D9488)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{t.heroLine2 || 'Never overpay.'}</span>
        </h1>

        <p style={{ fontSize: 15, color: 'var(--textmd)', lineHeight: 1.6, maxWidth: 300, margin: '0 auto 36px' }}>
          {t.heroDesc || 'Agada reads any medicine strip to find authenticity, side effects, and cheaper Jan Aushadhi alternatives instantly.'}
        </p>

        {/* Floating Scanner Graphic */}
        <div style={{ position: 'relative', width: 140, height: 140, marginBottom: 36, animation: 'fadeUp 0.8s ease 0.1s both' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'var(--greenlt)', borderRadius: 28, transform: 'rotate(-6deg)', opacity: 0.6 }} />
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: '#fff', border: '1.5px solid var(--border)', borderRadius: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(0,0,0,0.06)', transform: 'rotate(4deg)' }}>
            <span style={{ fontSize: 56 }}>💊</span>
          </div>
          <div style={{ position: 'absolute', top: '15%', left: '-15%', background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '4px 8px', fontSize: 12, fontWeight: 700, color: 'var(--green)', boxShadow: 'var(--shadow)', transform: 'rotate(-10deg)', animation: 'popIn 0.5s cubic-bezier(0.34,1.56,0.64,1) 0.5s both' }}>✓ Verified</div>
          <div style={{ position: 'absolute', bottom: '15%', right: '-15%', background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '4px 8px', fontSize: 12, fontWeight: 700, color: 'var(--textlt)', boxShadow: 'var(--shadow)', transform: 'rotate(8deg)', animation: 'popIn 0.5s cubic-bezier(0.34,1.56,0.64,1) 0.65s both' }}>₹40 Save</div>
        </div>

        {/* Primary Call to Action */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 12, animation: 'fadeUp 0.4s ease 0.3s both' }}>
          <button onClick={() => onCamera('medicine')} style={{ width: '100%', height: 60, background: 'linear-gradient(135deg, var(--green), #0D9488)', borderRadius: 16, color: '#fff', fontSize: 17, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, boxShadow: '0 8px 16px rgba(15,122,90,0.25)', border: 'none', cursor: 'pointer', transition: 'transform 0.2s' }}>
            <span style={{ fontSize: 22 }}>📷</span> {t.scanMedicineBtn || 'Scan Medicine Strip'}
          </button>
          
          <button onClick={() => onCamera('prescription')} style={{ width: '100%', height: 60, background: 'linear-gradient(135deg, var(--navy), var(--navylt))', borderRadius: 16, color: '#fff', fontSize: 17, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, boxShadow: '0 8px 16px rgba(26,43,74,0.25)', border: 'none', cursor: 'pointer', transition: 'transform 0.2s' }}>
            <span style={{ fontSize: 22 }}>📝</span> {t.scanPrescriptionBtn || 'Scan Prescription'}
          </button>

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => onUpload('medicine')} style={{ flex: 1, height: 44, background: 'rgba(255,255,255,0.7)', border: '1.5px solid var(--border)', borderRadius: 12, color: 'var(--textmd)', fontSize: 13, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)' }}>
              {t.uploadStrip || 'Upload Strip'}
            </button>
            <button onClick={() => onUpload('prescription')} style={{ flex: 1, height: 44, background: 'rgba(255,255,255,0.7)', border: '1.5px solid var(--border)', borderRadius: 12, color: 'var(--textmd)', fontSize: 13, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)' }}>
              {t.uploadRx || 'Upload Rx'}
            </button>
          </div>
        </div>
      </div>

      {/* Trust Badges */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, animation: 'fadeUp 0.5s ease 0.4s both' }}>
        {[
          ['🏛', 'CDSCO DB', '3,300+ tracked'],
          ['💸', 'Jan Aushadhi', 'Live mapping'],
          ['🛡️', 'AI Assistant', 'Instant insights'],
          ['🔒', 'Secure', 'Private scans']
        ].map(([icon, title, sub]) => (
          <div key={title} style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#fff', border: '1.5px solid var(--bgsoft)', borderRadius: 12, padding: '10px 12px', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            <div style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--bgsoft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>{icon}</div>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--navy)', lineHeight: 1.2 }}>{title}</div>
              <div style={{ fontSize: 10.5, color: 'var(--textlt)' }}>{sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Saved Scans Registry (QoL 3) */}
      {bookmarks && bookmarks.length > 0 && (
        <div style={{ marginTop: 24, marginBottom: 12, animation: 'fadeUp 0.5s ease 0.35s both' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--navy)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            📌 Saved Medicines ({bookmarks.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 180, overflowY: 'auto', paddingRight: 4 }}>
            {bookmarks.map((b, idx) => (
              <div
                key={idx}
                onClick={() => handleSelectBookmark(b)}
                style={{
                  background: '#fff',
                  border: '1.5px solid var(--border)',
                  borderRadius: 12,
                  padding: '10px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.01)',
                  transition: 'all 0.15s'
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.borderColor = 'var(--green)';
                  e.currentTarget.style.transform = 'translateY(-1px)';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)';
                  e.currentTarget.style.transform = 'none';
                }}
              >
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--greenlt)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, flexShrink: 0 }}>
                  💊
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--navy)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {b.brandName}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--textlt)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {b.saltComposition}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteBookmark(e, b)}
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: 'transparent',
                    color: 'var(--textlt)',
                    fontSize: 14,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    transition: 'color 0.2s'
                  }}
                  onMouseOver={(e) => e.currentTarget.style.color = 'var(--red)'}
                  onMouseOut={(e) => e.currentTarget.style.color = 'var(--textlt)'}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer links */}
      <div style={{ textAlign: 'center', padding: '16px 0 4px', display: 'flex', justifyContent: 'center', gap: 20 }}>
        <button onClick={() => setPage('privacy')} style={{ fontSize: 11.5, color: 'var(--textlt)', fontWeight: 500 }}>
          {t.privacyTitle || 'Privacy Policy'}
        </button>
        <button onClick={() => setPage('terms')} style={{ fontSize: 11.5, color: 'var(--textlt)', fontWeight: 500 }}>
          {t.termsTitle || 'Terms of Service'}
        </button>
      </div>
    </div>
  )
}

function LoadingView({ t, step, preview, barcodeHit }) {
  const steps = [
    { label: t.step1 || 'Reading medicine label', tag: t.tagGroq || 'Groq AI', done: step >= 1 },
    { label: barcodeHit ? '✓ Barcode / QR decoded' : (t.step2 || 'Scanning barcode / QR code'), tag: barcodeHit ? 'DECODED' : 'ZXing', done: step >= 2 },
    { label: t.step3 || 'Looking up CDSCO + Jan Aushadhi database', tag: t.tagCDSCO || 'Local DB', done: step >= 3 },
  ]
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 24px', animation: 'fadeIn 0.3s ease' }}>
      {preview && (
        <div style={{ width: 72, height: 72, borderRadius: 12, overflow: 'hidden', marginBottom: 20, border: '2px solid var(--border)', boxShadow: 'var(--shadow)' }}>
          <img src={preview} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      )}
      <div style={{ width: 52, height: 52, borderRadius: '50%', border: '3px solid var(--border)', borderTopColor: 'var(--green)', animation: 'spin 0.9s linear infinite', marginBottom: 18 }} />
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--navy)', marginBottom: 4 }}>{t.analysing || 'Analysing...'}</div>
      <div style={{ fontSize: 13, color: 'var(--textlt)', marginBottom: 28 }}>{t.checkingThree || 'Checking three sources at once'}</div>
      <div style={{ width: '100%', maxWidth: 360, display: 'flex', flexDirection: 'column', gap: 9 }}>
        {steps.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px', background: s.done ? 'var(--greenlt)' : 'var(--bgcard)', border: `1.5px solid ${s.done ? '#A7D9CA' : 'var(--border)'}`, borderRadius: 11, transition: 'all 0.4s ease' }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', background: s.done ? 'var(--green)' : 'var(--bgsoft)', border: `1.5px solid ${s.done ? 'var(--green)' : 'var(--bordermd)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: s.done ? '#fff' : 'var(--textlt)', fontWeight: 700, flexShrink: 0, transition: 'all 0.4s ease' }}>{s.done ? '✓' : i+1}</div>
            <span style={{ fontSize: 13, color: s.done ? 'var(--greendk)' : 'var(--textmd)', flex: 1, fontWeight: s.done ? 600 : 400 }}>{s.label}</span>
            <span style={{ fontSize: 9.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: s.done ? 'rgba(15,122,90,0.15)' : 'var(--bgsoft)', color: s.done ? 'var(--green)' : 'var(--textlt)', letterSpacing: '0.04em', transition: 'all 0.4s ease' }}>{s.tag}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ErrorView({ error, onReset, t }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 24px' }}>
      <div style={{ background: 'var(--redlt)', border: '1.5px solid #FECACA', borderRadius: 16, padding: '24px 20px', textAlign: 'center', width: '100%', maxWidth: 360 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--red)', marginBottom: 8 }}>{t.scanFailed || 'Scan failed'}</div>
        <p style={{ fontSize: 13, color: '#7F1D1D', lineHeight: 1.6, marginBottom: 20 }}>{error}</p>
        <button onClick={onReset} style={{ background: 'var(--red)', color: '#fff', padding: '12px 28px', borderRadius: 10, fontSize: 14, fontWeight: 600 }}>{t.tryAgain || 'Try Again'}</button>
      </div>
    </div>
  )
}
