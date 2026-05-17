import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Mail, PlusCircle, CheckCircle, ExternalLink, ChevronDown } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import DrugStatusCard from '../components/DrugStatusCard.jsx';
import { capitalize } from '../lib/utils.js';
import InteractionCard from '../components/InteractionCard.jsx';
import {
  getItemPresence,
  getModalCardPresence,
  getModalOverlayPresence,
  getPagePresence,
  getSwapPresence,
  LAYOUT_TRANSITION,
} from '../lib/motion.js';
import { streamAnalyzeDrug } from '../api/index.js';
import { fetchSession, fetchProfile, fetchRegimen, addDrugToRegimen } from '../lib/db.js';
import { SOURCE_META } from '../lib/constants.js';
import styles from './SessionPage.module.css';

function normalizeDrugKey(name) {
  return (name || '').toLowerCase().split('(')[0].trim();
}

function drugAliases(drug) {
  return [
    drug?.input_name,
    drug?.generic_name,
    ...(drug?.brand_names ?? []),
  ]
    .map(normalizeDrugKey)
    .filter(Boolean);
}

function formatAgentDecision(data) {
  const pair = data.pair ? data.pair.join(' / ') : '';
  switch (data.stage) {
    case 'drug_resolution':
      return `Resolving '${data.input}' → '${data.resolved_to}'…`;
    case 'quality_check':
      if (data.verdict === 'sufficient') return pair ? `Evidence verified for ${pair}.` : null;
      return pair ? `Researching further: ${(data.gaps || []).join(', ')} (${pair})` : null;
    case 'research_step':
      if (data.tool === 'done') return null;
      return pair ? `Agent searching ${data.tool?.replace('_', ' ')} for ${pair}…` : null;
    case 'synthesis_repair':
      return `Repairing synthesis output for ${pair}…`;
    case 'loop_cap_reached':
      return pair ? `Research complete for ${pair}.` : null;
    default:
      return null;
  }
}

export default function SessionPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();

  const {
    newDrug = 'Atorvastatin',
    regimen = [],
    doctor = 'Dr. Zhang',
    doctorEmail = 'zhang@stanfordhealth.org',
  } = location.state ?? {};

  const [phase, setPhase] = useState('loading');
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [synthesizedPairs, setSynthesizedPairs] = useState(new Map());
  const [totalPairs, setTotalPairs] = useState(0);
  const [cachedPairCount, setCachedPairCount] = useState(0);
  const [streamPhase, setStreamPhase] = useState('idle');
  const [sourceUpdates, setSourceUpdates] = useState([]);
  const [regimenAliases, setRegimenAliases] = useState({});
  const calledRef = useRef(false);

  const [addedToList, setAddedToList] = useState(false);
  const [addingToList, setAddingToList] = useState(false);
  const [showAddWarning, setShowAddWarning] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const [agentLines, setAgentLines] = useState([]);

  const [displayNewDrug, setDisplayNewDrug] = useState(null);
  const [displayRegimen, setDisplayRegimen] = useState(null);
  const [displayDoctor, setDisplayDoctor] = useState(null);
  const [displayDoctorEmail, setDisplayDoctorEmail] = useState(null);

  const activeNewDrug = displayNewDrug ?? newDrug;
  const activeRegimen = displayRegimen ?? regimen;
  const activeDoctor = displayDoctor ?? doctor;
  const activeDoctorEmail = displayDoctorEmail ?? doctorEmail;

  const pagePresence = getPagePresence(reducedMotion);
  const swapPresence = getSwapPresence(reducedMotion, 8);
  const itemPresence = getItemPresence(reducedMotion, 8, 0.99);
  const modalOverlayPresence = getModalOverlayPresence(reducedMotion);
  const modalCardPresence = getModalCardPresence(reducedMotion);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    if (id !== 'pending' && !location.state?.newDrug) {
      Promise.all([fetchSession(id), fetchProfile()])
        .then(([session, profile]) => {
          if (!session) { setError('Session not found.'); return; }
          setReport(session.report);
          const storedNew = session.new_drug ?? '';
          const storedRegimen = (session.report?.regimen ?? [])
            .map((d) => d.generic_name || d.input_name)
            .filter((name) => name.toLowerCase() !== storedNew.toLowerCase());
          setDisplayNewDrug(storedNew);
          setDisplayRegimen(storedRegimen);
          if (profile) {
            setDisplayDoctor(profile.doctor ?? '');
            setDisplayDoctorEmail(profile.doctor_email ?? '');
          }
          setPhase('done');
        })
        .catch((err) => setError(err.message));
      return;
    }

    streamAnalyzeDrug(newDrug.toLowerCase(), id !== 'pending' ? id : undefined, {
      onEvent({ type, data }) {
        if (type === 'intake_done') {
          setStreamPhase('intake');
          setTotalPairs(data.pairs?.length ?? 0);
          const targetAliases = new Set(
            (data.regimen ?? [])
              .filter((drug) => drugAliases(drug).includes(normalizeDrugKey(newDrug)))
              .flatMap(drugAliases)
          );
          const nextAliases = Object.fromEntries(
            activeRegimen.map((drugName) => {
              const displayKey = normalizeDrugKey(drugName);
              const matchedDrug = (data.regimen ?? []).find((drug) => {
                const aliases = drugAliases(drug);
                return aliases.includes(displayKey) && !aliases.some((alias) => targetAliases.has(alias));
              });
              const aliases = matchedDrug ? drugAliases(matchedDrug) : [displayKey];
              return [drugName, Array.from(new Set(aliases))];
            })
          );
          setRegimenAliases(nextAliases);
        } else if (type === 'memory_result') {
          const nextCached = data.cached_pairs?.length ?? 0;
          const nextNew = data.new_pairs?.length ?? 0;
          setCachedPairCount(nextCached);
          setStreamPhase(nextNew === 0 && nextCached > 0 ? 'cached' : 'synthesis');
        } else if (type === 'source_result') {
          setSourceUpdates((prev) => [...prev, data]);
          setStreamPhase('fanout');
        } else if (type === 'rate_limit') {
          setRateLimited(true);
        } else if (type === 'agent_decision') {
          const line = formatAgentDecision(data);
          if (line) setAgentLines((prev) => [...prev.slice(-2), line]);
        } else if (type === 'synthesis_result') {
          setRateLimited(false);
          const key = data.drug_pair.join('|');
          setSynthesizedPairs((prev) => new Map(prev).set(key, data));
        } else if (type === 'report_done') {
          setRateLimited(false);
          setReport(data.report);
          navigate(`/session/${data.session_id}`, { replace: true });
          setTimeout(() => setPhase('done'), 300);
        }
      },
      onError(err) { setError(err.message); },
    }).catch((err) => setError(err.message));
  }, [id, location.state, navigate, newDrug]);

  const PHASE_LABELS = {
    idle: 'Preparing analysis…',
    intake: 'Identifying drugs via RxNorm…',
    cached: `Using cached analysis for ${cachedPairCount} pair${cachedPairCount === 1 ? '' : 's'}…`,
    fanout: `Querying sources (${sourceUpdates.length} / ${totalPairs * 3})…`,
    synthesis: `Synthesizing interactions (${synthesizedPairs.size} / ${totalPairs})`,
    done: 'Analysis complete',
  };

  function isDrugDone(drugName) {
    const aliases = regimenAliases[drugName] ?? [normalizeDrugKey(drugName)];
    for (const key of synthesizedPairs.keys()) {
      if (key.split('|').some((pairDrug) => aliases.includes(normalizeDrugKey(pairDrug)))) return true;
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
        (drug) => (drug.generic_name || drug.input_name).toLowerCase() === activeNewDrug.toLowerCase()
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
      (interaction) => interaction.severity === 'major' || interaction.severity === 'contraindicated'
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

  return (
    <div className={styles.page}>
      <motion.div
        className={styles.centerPanel}
        initial={pagePresence.initial}
        animate={pagePresence.animate}
        exit={pagePresence.exit}
      >
        <AnimatePresence mode="wait">
          {error ? (
            <motion.div
              key="session-error"
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              <button className="btn-ghost" onClick={() => navigate('/')}>
                <ArrowLeft size={16} /> Home
              </button>
              <p className={`${styles.errorMsg} mt-16`}>{error}</p>
            </motion.div>
          ) : phase === 'loading' ? (
            <motion.div
              key="session-loading"
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              <button className="btn-ghost mb-24" onClick={() => navigate('/')}>
                <ArrowLeft size={16} /> Home
              </button>
              <p className="text-section-label">We are researching the possible drug interactions for:</p>
              <h1 className="text-title mt-4">{capitalize(activeNewDrug)}</h1>
              <p className={`${styles.loadingNote} mt-8`}>{PHASE_LABELS[streamPhase]}</p>
              <AnimatePresence mode="popLayout">
                {agentLines.map((line, i) => (
                  <motion.p
                    key={line}
                    className={styles.agentLine}
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2, delay: i * 0.05 }}
                  >
                    {line}
                  </motion.p>
                ))}
              </AnimatePresence>
              <AnimatePresence>
                {rateLimited && (
                  <motion.p
                    className={styles.rateLimitNote}
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.25 }}
                  >
                    This service is maintained for free — rate limits keep the AI model accessible to everyone. Hang tight while we wait for the next available slot.
                  </motion.p>
                )}
              </AnimatePresence>

              <div className={styles.cardsRow}>
                {activeRegimen.map((drug) => {
                  const isDone = isDrugDone(drug);
                  const aliases = regimenAliases[drug] ?? [normalizeDrugKey(drug)];
                  const drugSources = sourceUpdates.filter((update) =>
                    update.pair.some((pairDrug) => aliases.includes(normalizeDrugKey(pairDrug)))
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
            </motion.div>
          ) : (
            <ReportView
              key="session-report"
              report={report}
              activeNewDrug={activeNewDrug}
              activeRegimen={activeRegimen}
              activeDoctor={activeDoctor}
              activeDoctorEmail={activeDoctorEmail}
              addedToList={addedToList}
              addingToList={addingToList}
              handleAddToList={handleAddToList}
              navigate={navigate}
              itemPresence={itemPresence}
              reducedMotion={reducedMotion}
            />
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence>
        {showAddWarning && (
          <motion.div
            className={styles.warningOverlay}
            onClick={() => setShowAddWarning(false)}
            initial={modalOverlayPresence.initial}
            animate={modalOverlayPresence.animate}
            exit={modalOverlayPresence.exit}
          >
            <motion.div
              className={styles.warningModal}
              onClick={(e) => e.stopPropagation()}
              initial={modalCardPresence.initial}
              animate={modalCardPresence.animate}
              exit={modalCardPresence.exit}
            >
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
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ReportView({
  report,
  activeNewDrug,
  activeRegimen,
  activeDoctor,
  activeDoctorEmail,
  addedToList,
  addingToList,
  handleAddToList,
  navigate,
  itemPresence,
  reducedMotion,
}) {
  const swapPresence = getSwapPresence(reducedMotion, 8);
  const topMajor = report.interactions.find(
    (interaction) => interaction.severity === 'major' || interaction.severity === 'contraindicated'
  );

  return (
    <motion.div
      initial={swapPresence.initial}
      animate={swapPresence.animate}
      exit={swapPresence.exit}
    >
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
        reducedMotion={reducedMotion}
      />

      {report.sources_consulted?.length > 0 && (
        <div className={styles.sourcesSection}>
          <p className={styles.sectionHeading}>Sources consulted:</p>
          <div className={styles.sourcesGrid}>
            {report.sources_consulted.map((source) => {
              const meta = SOURCE_META[source] || { label: source, url: '#', domain: null };
              return (
                <motion.a
                  key={source}
                  href={meta.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.sourceCard}
                  initial={itemPresence.initial}
                  animate={itemPresence.animate}
                  exit={itemPresence.exit}
                >
                  {meta.domain && (
                    <img
                      src={`https://www.google.com/s2/favicons?domain=${meta.domain}&sz=16`}
                      width={14}
                      height={14}
                      alt=""
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

      <motion.div className={styles.summaryStrip} layout transition={LAYOUT_TRANSITION}>
        {activeRegimen.map((drug) => {
          const danger = report.interactions.some(
            (interaction) =>
              interaction.drug_pair.includes(drug.toLowerCase()) &&
              (interaction.severity === 'major' || interaction.severity === 'contraindicated')
          );

          return (
            <motion.div
              key={drug}
              layout
              transition={LAYOUT_TRANSITION}
              initial={itemPresence.initial}
              animate={itemPresence.animate}
              exit={itemPresence.exit}
            >
              <InteractionCard
                compact
                interaction={{
                  drug_pair: [drug, activeNewDrug],
                  severity: danger ? 'major' : 'no_concern',
                  headline: '',
                }}
              />
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}

function InteractionGroups({ interactions, newDrug, reducedMotion }) {
  const [noConcernOpen, setNoConcernOpen] = useState(false);
  const swapPresence = getSwapPresence(reducedMotion, 6);
  const itemPresence = getItemPresence(reducedMotion, 8, 0.99);

  const buckets = [
    { key: 'danger', label: 'Major', severities: ['contraindicated', 'major'] },
    { key: 'moderate', label: 'Moderate', severities: ['moderate'] },
    { key: 'minor', label: 'Minor', severities: ['minor'] },
    { key: 'no_concern', label: 'No concern', severities: ['no_concern'] },
  ];

  const grouped = buckets
    .map((bucket) => ({
      ...bucket,
      items: interactions.filter((interaction) => bucket.severities.includes(interaction.severity)),
    }))
    .filter((bucket) => bucket.items.length > 0);

  return (
    <div className={styles.interactionGroups}>
      {grouped.map((bucket) => {
        const isNoConcern = bucket.key === 'no_concern';
        const count = bucket.items.length;
        const DividerTag = isNoConcern ? 'button' : 'div';

        return (
          <motion.div
            key={bucket.key}
            className={styles.groupSection}
            layout
            transition={LAYOUT_TRANSITION}
          >
            <DividerTag
              className={`${styles.groupDivider} ${styles[`divider_${bucket.key}`]}`}
              {...(isNoConcern ? { onClick: () => setNoConcernOpen((open) => !open) } : {})}
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

            <AnimatePresence>
              {(!isNoConcern || noConcernOpen) && (
                <motion.div
                  key={`${bucket.key}-${isNoConcern ? 'open' : 'static'}`}
                  className={styles.groupRows}
                  layout
                  transition={LAYOUT_TRANSITION}
                  initial={isNoConcern ? swapPresence.initial : false}
                  animate={isNoConcern ? swapPresence.animate : undefined}
                  exit={isNoConcern ? swapPresence.exit : undefined}
                >
                  <AnimatePresence>
                    {bucket.items.map((interaction) => (
                      <motion.div
                        key={interaction.drug_pair.join('-')}
                        layout
                        transition={LAYOUT_TRANSITION}
                        initial={itemPresence.initial}
                        animate={itemPresence.animate}
                        exit={itemPresence.exit}
                      >
                        <InteractionCard interaction={interaction} newDrug={newDrug} />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </div>
  );
}
