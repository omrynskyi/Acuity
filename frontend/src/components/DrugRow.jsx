import styles from './DrugRow.module.css';
import { capitalize } from '../lib/utils.js';

export default function DrugRow({ drug }) {
  const name = drug.generic_name || drug.input_name;
  const dose = drug.dose ?? '';
  const freq = drug.frequency && drug.frequency !== 'daily' ? (drug.custom_frequency || drug.frequency) : null;

  return (
    <div className={styles.row}>
      <span className={styles.name}>{capitalize(name)}</span>
      <div className={styles.meta}>
        {dose && <span className={styles.dose}>{dose}</span>}
        {freq && <span className={styles.freq}>{freq}</span>}
      </div>
    </div>
  );
}
