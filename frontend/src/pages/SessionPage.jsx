import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Mail } from 'lucide-react';
import DrugStatusCard from '../components/DrugStatusCard.jsx';
import InteractionCard from '../components/InteractionCard.jsx';
import { analyzeRegimen, getSourceFindings } from '../api/index.js';
import fixtures from '../data/fixtures.json';
import styles from './SessionPage.module.css';

const SOURCES = [
  { label: 'openFDA', icon: '🔬', url: 'https://open.fda.gov/' },
  { label: 'PubMed',  icon: '🌐', url: 'https://pubmed.ncbi.nlm.nih.gov/' },
];

const STAGGER_MS = 700;

export default function SessionPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const { newDrug = 'Atorvastatin', regimen = [] } = location.state ?? {};

  const [phase, setPhase] = useState('loading');
  const [doneCount, setDoneCount] = useState(0);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const calledRef = useRef(false);

  const existingDrugs = regimen.length > 0
    ? regimen
    : fixtures.regimen_report.regimen.map((d) => d.generic_name || d.input_name);

  const sourceFindings = getSourceFindings();

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    const allDrugs = [...existingDrugs, newDrug.toLowerCase()];

    analyzeRegimen(allDrugs, id !== 'pending' ? id : undefined)
      .then(({ session_id, report: r }) => {
        setReport(r);
        existingDrugs.forEach((_, i) => {
          setTimeout(() => setDoneCount((c) => c + 1), (i + 1) * STAGGER_MS);
        });
        setTimeout(() => {
          navigate(`/session/${session_id}`, { replace: true, state: location.state });
          setPhase('done');
        }, (existingDrugs.length + 1) * STAGGER_MS + 400);
      })
      .catch((err) => setError(err.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function snippetForDrug(drugName) {
    const finding = sourceFindings.find(
      (f) => f.drug_pair.includes(drugName.toLowerCase()) && f.findings.length > 0
    );
    return finding ? finding.findings[0].description : 'This drug is a good match';
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className="container">
          <button className="btn-ghost" onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Home
          </button>
          <p className={`${styles.errorMsg} mt-16`}>{error}</p>
        </div>
      </div>
    );
  }

  /* ── Loading ─────────────────────────────────────────────────────────── */

  if (phase === 'loading') {
    return (
      <div className={styles.page}>
        <div className="container">
          <button className="btn-ghost mb-24" onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Home
          </button>
          <p className="text-section-label">We are researching the possible drug interactions for:</p>
          <h1 className="text-title mt-4">{capitalize(newDrug)}</h1>
          <p className={`${styles.loadingNote} mt-8`}>Your full report will appear here after research is done</p>
        </div>

        <div className={styles.cardsRow}>
          {existingDrugs.map((drug, i) => {
            const isDone = i < doneCount;
            const span = bentoSpan(i, existingDrugs.length);
            return (
              <div key={drug} style={span > 1 ? { gridColumn: `span ${span}` } : undefined}>
                <DrugStatusCard
                  drugName={drug}
                  status={isDone ? 'done' : 'progress'}
                  snippet={isDone ? snippetForDrug(drug) : undefined}
                  sources={!isDone ? SOURCES : undefined}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  /* ── Report ──────────────────────────────────────────────────────────── */

  const r = report ?? fixtures.regimen_report;
  const topMajor = r.interactions.find(
    (ix) => ix.severity === 'major' || ix.severity === 'contraindicated'
  );

  return (
    <div className={styles.page}>
      <div className="container">
        <button className="btn-ghost mb-24" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> Home
        </button>

        <p className="text-section-label">Your Drug Interaction Report for:</p>
        <h1 className="text-title mt-4">{capitalize(newDrug)}</h1>

        {r.patient_friendly_summary && (
          <p className="text-body mt-16 mb-24">{r.patient_friendly_summary}</p>
        )}

        {topMajor && (
          <div className={styles.dangerAlert}>
            <AlertCircle size={18} className={styles.alertIcon} />
            <div>
              <p className={styles.dangerHeadline}>Do not start taking this new medication.</p>
              <p className={styles.dangerSub}>
                Contact your prescribing doctor immediately to discuss alternative treatments.
              </p>
            </div>
          </div>
        )}

        {/* Doctor card — uses design system .card */}
        <div className="card mb-32" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className={styles.doctorLeft}>
            <div className={styles.gmailIcon}>M</div>
            <div>
              <p className="text-body" style={{ fontWeight: 600 }}>Dr. Zhang</p>
              <p className="text-secondary">zhang@stanfordhealth.org</p>
            </div>
          </div>
          <button className="btn-primary">
            <Mail size={14} /> Send Report
          </button>
        </div>

        {topMajor && (
          <>
            <p className={styles.sectionHeading}>What is happening:</p>
            <p className="text-body">{topMajor.reasoning}</p>

            <p className={styles.sectionHeading}>Watch for these symptoms:</p>
            <p className="text-body">
              If you have already taken both medications, go to an emergency room if you experience
              severe muscle pain, sudden difficulty breathing, dizziness, or a feeling of extreme
              cold in your hands and feet.
            </p>
          </>
        )}

        <p className={styles.sectionHeading}>All interactions checked:</p>
        <div className={styles.interactionList}>
          {r.interactions.map((ix) => (
            <InteractionCard key={ix.drug_pair.join('-')} interaction={ix} />
          ))}
        </div>

        <div className={styles.summaryStrip}>
          {existingDrugs.map((drug) => {
            const danger = r.interactions.some(
              (ix) =>
                ix.drug_pair.includes(drug.toLowerCase()) &&
                (ix.severity === 'major' || ix.severity === 'contraindicated')
            );
            return (
              <InteractionCard
                key={drug}
                compact
                interaction={{
                  drug_pair: [drug, newDrug],
                  severity: danger ? 'major' : 'no_concern',
                  headline: '',
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Returns the grid-column span for card at `index` out of `total`,
// so the last incomplete row always fills all 3 columns (bento style).
function bentoSpan(index, total) {
  const COLS = 3;
  const remainder = total % COLS;
  if (remainder === 0) return 1;            // perfect grid, no spanning needed
  const lastRowStart = total - remainder;
  if (index < lastRowStart) return 1;       // not in the last row
  if (remainder === 1) return 3;            // lone card → full width
  // remainder === 2: split as 1 + 2 so the last card is wider
  return index === lastRowStart ? 1 : 2;
}
