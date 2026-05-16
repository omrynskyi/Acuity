import { CheckCircle, Loader2, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { SOURCE_META } from '../lib/constants.js';
import styles from './DrugStatusCard.module.css';

// Show only the 3 most recent source events — card height is fixed
const VISIBLE_COUNT = 3;

export default function DrugStatusCard({ drugName, status, sources = [], snippet }) {
  const isDone = status === 'done';
  const visibleSources = sources.slice(-VISIBLE_COUNT);

  return (
    <div className={`${styles.card} ${isDone ? styles.done : ''}`}>
      <div className={styles.header}>
        <span className={styles.name}>{capitalize(drugName)}</span>
        <span className={`${styles.status} ${isDone ? styles.statusDone : styles.statusProgress}`}>
          {isDone ? (
            <>Done <CheckCircle size={14} /></>
          ) : (
            <>In Progress <Loader2 size={14} className={styles.spin} /></>
          )}
        </span>
      </div>

      {/* Sources area is always present to keep card height stable */}
      <div className={styles.sources}>
        {isDone && snippet && (
          <p className={styles.snippet}>{snippet}</p>
        )}
        <AnimatePresence initial={false}>
          {!isDone && visibleSources.map((u) => {
            const meta = SOURCE_META[u.source] ?? { label: u.source, url: '#', domain: null };
            return (
              <motion.div
                key={`${u.source}-${u.pair.join('-')}`}
                className={styles.sourceEntry}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
              >
                {meta.domain && (
                  <img
                    className={styles.favicon}
                    src={`https://www.google.com/s2/favicons?domain=${meta.domain}&sz=16`}
                    alt=""
                    width={14}
                    height={14}
                  />
                )}
                <span className={styles.sourceLabel}>{meta.label}</span>
                <span className={styles.sourcePair}>{u.pair.join(' + ')}</span>
                {u.n_findings > 0 && (
                  <span className={styles.sourceFindings}>
                    {u.n_findings} finding{u.n_findings !== 1 ? 's' : ''}
                  </span>
                )}
                {meta.url !== '#' && (
                  <a
                    href={meta.url}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.sourceViewBtn}
                    onClick={e => e.stopPropagation()}
                  >
                    View <ExternalLink size={10} />
                  </a>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
