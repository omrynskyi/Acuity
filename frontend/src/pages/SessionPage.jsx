import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Mail, PlusCircle, CheckCircle, ExternalLink, ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';
import DrugStatusCard from '../components/DrugStatusCard.jsx';
import { capitalize } from '../lib/utils.js';
import InteractionCard from '../components/InteractionCard.jsx';
import { streamAnalyzeDrug } from '../api/index.js';
import { fetchSession, fetchProfile, fetchRegimen, addDrugToRegimen } from '../lib/db.js';
import { SOURCE_META } from '../lib/constants.js';
import styles from './SessionPage.module.css';

const STAGGER_MS = 700;

export default function SessionPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const {
    newDrug = 'Atorvastatin',
    regimen = [],
    profileId = null,
    doctor = 'Dr. Zhang',
    doctorEmail = 'zhang@stanfordhealth.org',
  } = location.state ?? {};

  const [phase, setPhase] = useState('loading');
  const [doneCount, setDoneCount] = useState(0);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [synthesizedPairs, setSynthesizedPairs] = useState(new Map());
  const [totalPairs, setTotalPairs] = useState(0);
  const [streamPhase, setStreamPhase] = useState('idle');
  const [sourceUpdates, setSourceUpdates] = useState([]);
  const calledRef = useRef(false);

  const [addedToList, setAddedToList] = useState(false);
  const [addingToList, setAddingToList] = useState(false);
  const [showAddWarning, setShowAddWarning] = useState(false);

  // Overrides populated when loading a saved report (no router state).
  const [displayNewDrug, setDisplayNewDrug] = useState(null);
  const [displayRegimen, setDisplayRegimen] = useState(null);
  const [displayDoctor, setDisplayDoctor] = useState(null);
  const [displayDoctorEmail, setDisplayDoctorEmail] = useState(null);

  const activeNewDrug = displayNewDrug ?? newDrug;
  const activeRegimen = displayRegimen ?? regimen;
  const activeDoctor = displayDoctor ?? doctor;
  const activeDoctorEmail = displayDoctorEmail ?? doctorEmail;

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    // Saved-report mode: real session id with no incoming navigation state.
    // Load the persisted report from Supabase without re-running analysis.
    if (id !== 'pending' && !location.state?.newDrug) {
      Promise.all([fetchSession(id), fetchProfile()])
        .then(([session, profile]) => {
          if (!session) { setError('Session not found.'); return; }
          setReport(session.report);
          // Derive display values from stored data
          const storedNew = session.new_drug ?? '';
          const storedRegimen = (session.report?.regimen ?? [])
            .map((d) => d.generic_name || d.input_name)
            .filter((n) => n.toLowerCase() !== storedNew.toLowerCase());
          setDisplayNewDrug(storedNew);
          setDisplayRegimen(storedRegimen);
          if (profile) { setDisplayDoctor(profile.doctor ?? ''); setDisplayDoctorEmail(profile.doctor_email ?? ''); }
          setPhase('done');
        })
        .catch((err) => setError(err.message));
      return;
    }

    // Fresh-analysis mode: stream from backend.
    // Use the drug-specific endpoint so only pairs involving the new drug are checked,
    // not every existing-regimen pair.
    streamAnalyzeDrug(newDrug.toLowerCase(), id !== 'pending' ? id : undefined, {
      onEvent({ type, data }) {
        if (type === 'intake_done') {
          setStreamPhase('intake');
          setTotalPairs(data.pairs?.length ?? 0);
        } else if (type === 'memory_result') {
          setStreamPhase('synthesis');
        } else if (type === 'source_result') {
          setSourceUpdates((prev) => [...prev, data]);
          setStreamPhase('fanout');
        } else if (type === 'synthesis_result') {
          const key = data.drug_pair.join('|');
          setSynthesizedPairs((prev) => new Map(prev).set(key, data));
          setDoneCount((c) => c + 1);
        } else if (type === 'report_done') {
          setReport(data.report);
          navigate(`/session/${data.session_id}`, { replace: true, state: location.state });
          setTimeout(() => setPhase('done'), 300);
        }
      },
      onError(err) { setError(err.message); },
    }).catch((err) => setError(err.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const PHASE_LABELS = {
    idle: 'Preparing analysis…',
    intake: 'Identifying drugs via RxNorm…',
    fanout: `Querying sources (${sourceUpdates.length} / ${totalPairs * 3})…`,
    synthesis: `Synthesizing interactions (${synthesizedPairs.size} / ${totalPairs})`,
    done: 'Analysis complete',
  };

  function isDrugDone(drugName) {
    const lower = drugName.toLowerCase();
    for (const key of synthesizedPairs.keys()) {
      if (key.split('|').includes(lower)) return true;
    }
    return false;
  }

  async function doAddToList() {
    if (!report) return;
    setAddingToList(true);
    try {
      const profile = await fetchProfile();
      if (!profile) return;
      const existing = await fetchRegimen(profile.id);
      const alreadyIn = existing.some(
        d => (d.generic_name || d.input_name).toLowerCase() === activeNewDrug.toLowerCase()
      );
      if (!alreadyIn) {
        await addDrugToRegimen(profile.id, {
          input_name: activeNewDrug.toLowerCase(),
          generic_name: activeNewDrug.toLowerCase(),
          dose: null,
          frequency: 'daily',
          sort_order: existing.length,
        });
      }
      setAddedToList(true);
    } finally {
      setAddingToList(false);
      setShowAddWarning(false);
    }
  }

  function handleAddToList() {
    if (!report) return;
    const hasDanger = report.interactions.some(
      ix => ix.severity === 'major' || ix.severity === 'contraindicated'
    );
    if (hasDanger) {
      setShowAddWarning(true);
    } else {
      doAddToList();
    }
  }

  function sendToDoctor() {
    const subject = encodeURIComponent(`Drug Interaction Alert: ${capitalize(activeNewDrug)}`);
    const body = encodeURIComponent(
      `Dear ${activeDoctor},\n\nI am considering adding ${capitalize(activeNewDrug)} to my current regimen and the Acuity interaction checker flagged a dangerous interaction.\n\nCould you please review this before I proceed?\n\nThank you.`
    );
    window.open(`mailto:${activeDoctorEmail}?subject=${subject}&body=${body}`);
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
        <div className={styles.centerPanel}>
          <button className="btn-ghost mb-24" onClick={() => navigate('/')}>
            <ArrowLeft size={16} /> Home
          </button>
          <p className="text-section-label">We are researching the possible drug interactions for:</p>
          <h1 className="text-title mt-4">{capitalize(activeNewDrug)}</h1>
          <p className={`${styles.loadingNote} mt-8`}>{PHASE_LABELS[streamPhase]}</p>

          <div className={styles.cardsRow}>
            {activeRegimen.map((drug) => {
              const isDone = isDrugDone(drug);
              const baseDrug = drug.toLowerCase().split('(')[0].trim();
              const drugSources = sourceUpdates.filter(u =>
                u.pair.some(p => {
                  const pl = p.toLowerCase();
                  return pl === baseDrug || pl.includes(baseDrug) || baseDrug.includes(pl);
                })
              );
              return (
                <DrugStatusCard
                  key={drug}
                  drugName={drug}
                  status={isDone ? 'done' : 'progress'}
                  sources={drugSources}
                  snippet={isDone ? 'Analysis complete' : undefined}
                />
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  /* ── Report ──────────────────────────────────────────────────────────── */

  const topMajor = report.interactions.find(
    (ix) => ix.severity === 'major' || ix.severity === 'contraindicated'
  );

  return (
    <div className={styles.page}>
      <div className={styles.centerPanel}>
        <button className="btn-ghost mb-24" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> Home
        </button>

        <div className={styles.reportTitleRow}>
          <div>
            <p className="text-section-label">Your Drug Interaction Report for:</p>
            <h1 className="text-title mt-4">{capitalize(activeNewDrug)}</h1>
          </div>
          <button
            className={`${styles.addToListBtn} ${addedToList ? styles.addedBtn : ''}`}
            onClick={handleAddToList}
            disabled={addingToList || addedToList}
          >
            {addedToList
              ? <><CheckCircle size={15} /> Added to My Medicine List</>
              : addingToList
              ? 'Adding…'
              : <><PlusCircle size={15} /> Add to My Medicine List</>
            }
          </button>
        </div>

        {report.patient_friendly_summary && (
          <p className="text-body mt-16 mb-24">{report.patient_friendly_summary}</p>
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

        <div className="card mb-32" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className={styles.doctorLeft}>
            <img src="/gmail.png" alt="Gmail" className={styles.gmailIcon} />
            <div>
              <p className="text-body" style={{ fontWeight: 600 }}>{activeDoctor}</p>
              <p className="text-secondary">{activeDoctorEmail}</p>
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
              If you have already taken {capitalize(topMajor.drug_pair[0])} and{' '}
              {capitalize(topMajor.drug_pair[1])} together, watch for any unusual or
              severe symptoms and seek emergency care immediately if you feel unwell.
            </p>
          </>
        )}

        <p className={styles.sectionHeading}>
          Interactions with {capitalize(activeNewDrug)}:
        </p>
        <InteractionGroups
          interactions={report.interactions}
          newDrug={activeNewDrug.toLowerCase()}
        />

        {report.sources_consulted?.length > 0 && (
          <div className={styles.sourcesSection}>
            <p className={styles.sectionHeading}>Sources consulted:</p>
            <div className={styles.sourcesGrid}>
              {report.sources_consulted.map((s, i) => {
                const meta = SOURCE_META[s] || { label: s, url: '#', domain: null };
                return (
                  <motion.a
                    key={s}
                    href={meta.url}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.sourceCard}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.32, ease: 'easeOut', delay: i * 0.08 }}
                  >
                    {meta.domain && (
                      <img
                        src={`https://www.google.com/s2/favicons?domain=${meta.domain}&sz=16`}
                        width={14} height={14} alt=""
                        className={styles.sourceCardFavicon}
                      />
                    )}
                    <span className={styles.sourceCardLabel}>{meta.label}</span>
                    <ExternalLink size={11} className={styles.sourceCardIcon} />
                  </motion.a>
                );
              })}
            </div>
          </div>
        )}

        <div className={styles.summaryStrip}>
          {activeRegimen.map((drug) => {
            const danger = report.interactions.some(
              (ix) =>
                ix.drug_pair.includes(drug.toLowerCase()) &&
                (ix.severity === 'major' || ix.severity === 'contraindicated')
            );
            return (
              <InteractionCard
                key={drug}
                compact
                interaction={{
                  drug_pair: [drug, activeNewDrug],
                  severity: danger ? 'major' : 'no_concern',
                  headline: '',
                }}
              />
            );
          })}
        </div>
      </div>

      {showAddWarning && (
        <div className={styles.warningOverlay} onClick={() => setShowAddWarning(false)}>
          <div className={styles.warningModal} onClick={e => e.stopPropagation()}>
            <div className={styles.warningModalHeader}>
              <AlertCircle size={18} className={styles.warningModalIcon} />
              <h2 className={styles.warningModalTitle}>Dangerous Combination</h2>
            </div>
            <p className={styles.warningModalBody}>
              {capitalize(activeNewDrug)} has a dangerous interaction with your current medications.
              Contact your doctor before starting this medication.
            </p>

            {activeDoctorEmail && (
              <div className={styles.warningDoctorCard}>
                <div className={styles.warningDoctorInfo}>
                  <p className={styles.warningDoctorName}>{activeDoctor}</p>
                  <p className={styles.warningDoctorEmail}>{activeDoctorEmail}</p>
                </div>
                <button className={styles.warningDoctorSendBtn} onClick={sendToDoctor}>
                  <Mail size={13} /> Send Message
                </button>
              </div>
            )}

            <div className={styles.warningModalActions}>
              <button className={styles.warningCancelBtn} onClick={() => setShowAddWarning(false)}>
                Cancel
              </button>
              <button className={styles.warningAddBtn} onClick={doAddToList} disabled={addingToList}>
                {addingToList ? 'Adding…' : 'Add Anyway'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InteractionGroups({ interactions, newDrug }) {
  const [noConcernOpen, setNoConcernOpen] = useState(false);

  const BUCKETS = [
    { key: 'danger',     label: 'Major',      severities: ['contraindicated', 'major'] },
    { key: 'moderate',   label: 'Moderate',   severities: ['moderate'] },
    { key: 'minor',      label: 'Minor',      severities: ['minor'] },
    { key: 'no_concern', label: 'No concern', severities: ['no_concern'] },
  ];

  const grouped = BUCKETS.map(b => ({
    ...b,
    items: interactions.filter(ix => b.severities.includes(ix.severity)),
  })).filter(b => b.items.length > 0);

  return (
    <div className={styles.interactionGroups}>
      {grouped.map((bucket) => {
        const isNoConcern = bucket.key === 'no_concern';
        const count = bucket.items.length;
        const DividerTag = isNoConcern ? 'button' : 'div';

        return (
          <div key={bucket.key} className={styles.groupSection}>
            <DividerTag
              className={`${styles.groupDivider} ${styles[`divider_${bucket.key}`]}`}
              {...(isNoConcern ? { onClick: () => setNoConcernOpen(o => !o) } : {})}
            >
              <span className={styles.groupDot} />
              <span className={styles.groupTitle}>{bucket.label}</span>
              <span className={styles.groupCount}>
                {count} interaction{count !== 1 ? 's' : ''}
              </span>
              <span className={styles.groupLine} />
              {isNoConcern && (
                <ChevronDown
                  size={13}
                  className={`${styles.groupChevron} ${noConcernOpen ? styles.groupChevronOpen : ''}`}
                />
              )}
            </DividerTag>

            {(!isNoConcern || noConcernOpen) && (
              <div className={styles.groupRows}>
                {bucket.items.map((ix, i) => (
                  <motion.div
                    key={ix.drug_pair.join('-')}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, ease: 'easeOut', delay: i * 0.04 }}
                  >
                    <InteractionCard interaction={ix} newDrug={newDrug} />
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}


