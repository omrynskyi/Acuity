import { CheckCircle, Loader2 } from 'lucide-react';
import styles from './DrugStatusCard.module.css';

export default function DrugStatusCard({ drugName, status, sources, snippet }) {
  const isDone = status === 'done';

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

      {isDone && snippet && (
        <p className={styles.snippet}>{snippet}</p>
      )}

      {!isDone && sources && sources.length > 0 && (
        <div className={styles.sources}>
          <p className={styles.searchingLabel}>Searching:</p>
          {sources.map((src) => (
            <div key={src.label} className={styles.sourceChip}>
              <span className={styles.sourceIcon}>{src.icon}</span>
              <span className={styles.sourceUrl}>{src.url}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
