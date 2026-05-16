import styles from './SeverityBadge.module.css';

const LABELS = {
  contraindicated: 'Contraindicated',
  major: 'Major',
  moderate: 'Moderate',
  minor: 'Minor',
  no_concern: 'Safe',
};

export default function SeverityBadge({ severity }) {
  return (
    <span className={`${styles.badge} ${styles[severity]}`}>
      {LABELS[severity] ?? severity}
    </span>
  );
}
