import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { AlertCircle, CheckCircle, ChevronDown, ExternalLink } from 'lucide-react';
import { getSwapPresence } from '../lib/motion.js';
import SeverityBadge from './SeverityBadge.jsx';
import styles from './InteractionCard.module.css';

const SOURCE_LABELS = {
  openfda_label: 'FDA Label',
  openfda_faers: 'FDA FAERS',
  twosides: 'TWOSIDES',
  decagon: 'DECAGON',
  arxiv: 'arXiv',
  brave_search: 'Brave Search',
};

export default function InteractionCard({ interaction, compact, newDrug }) {
  const [open, setOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const [drugA, drugB] = interaction.drug_pair;
  const isMajor = interaction.severity === 'major' || interaction.severity === 'contraindicated';
  const swapPresence = getSwapPresence(reducedMotion, 6);

  /* ── Compact (bottom strip) ── */
  if (compact) {
    return (
      <motion.div
        className={`${styles.compact} ${isMajor ? styles.compactDanger : ''}`}
      >
        <div className={styles.compactHeader}>
          <span className={styles.compactName}>{cap(drugA)} + {cap(drugB)}</span>
          {isMajor
            ? <AlertCircle size={16} color="var(--color-red)" />
            : <CheckCircle size={16} color="var(--color-green)" />}
        </div>
        <span className={styles.compactLabel}>
          {isMajor ? 'Dangerous Combination' : 'This drug is a good match'}
        </span>
      </motion.div>
    );
  }

  /* ── Full accordion row ── */
  const newDrugLower = newDrug?.toLowerCase();
  const hasCitations = interaction.citations && interaction.citations.length > 0;

  function renderDrug(name) {
    const isNew = newDrugLower && name.toLowerCase() === newDrugLower;
    return (
      <span key={name} className={styles.drugName}>
        {cap(name)}
        {isNew && <span className={styles.newPill}>New</span>}
      </span>
    );
  }

  return (
    <motion.div className={styles.row}>
      <button
        className={styles.rowBtn}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={styles.rowLeft}>
          <span className={styles.drugPair}>
            {renderDrug(drugA)}
            <span className={styles.pairSep}> + </span>
            {renderDrug(drugB)}
          </span>
          <span className={styles.rowHeadline}>{interaction.headline}</span>
        </span>
        <span className={styles.rowRight}>
          <SeverityBadge severity={interaction.severity} />
          <ChevronDown
            size={15}
            className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}
          />
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className={styles.expanded}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={reducedMotion ? { duration: 0.08 } : { duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <motion.div
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              {interaction.reasoning && (
                <p className={styles.expandedReasoning}>{interaction.reasoning}</p>
              )}

              {hasCitations && (
                <div className={styles.evidence}>
                  <p className={styles.evidenceLabel}>Evidence</p>
                  <div className={styles.citationList}>
                    {interaction.citations.map((c, i) => (
                      <div key={i} className={styles.citation}>
                        <span className={styles.citationSource}>
                          {SOURCE_LABELS[c.source] ?? c.source}
                        </span>
                        <span className={styles.citationQuote}>"{c.quote}"</span>
                        {c.source_url && (
                          <a
                            href={c.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className={styles.citationLink}
                            onClick={e => e.stopPropagation()}
                          >
                            <ExternalLink size={11} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function cap(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}
