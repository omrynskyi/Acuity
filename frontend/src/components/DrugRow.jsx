import styles from './DrugRow.module.css';

const DOSES = {
  warfarin: '5mg',
  aspirin: '81mg',
  metformin: '500mg',
  lisinopril: '10mg',
  fluoxetine: '20mg',
  tramadol: '50mg',
  atorvastatin: '40mg',
};

export default function DrugRow({ drug, onEdit }) {
  const name = drug.generic_name || drug.input_name;
  const dose = DOSES[name.toLowerCase()] ?? '';

  return (
    <div className={styles.row}>
      <span className={styles.name}>{capitalize(name)}</span>
      <span className={styles.dose}>{dose}</span>
      {onEdit && (
        <button className={styles.edit} onClick={() => onEdit(drug)} aria-label="Edit">
          ✎
        </button>
      )}
    </div>
  );
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
