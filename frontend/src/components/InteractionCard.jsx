import { AlertCircle, CheckCircle, ExternalLink } from 'lucide-react';
import SeverityBadge from './SeverityBadge.jsx';
import styles from './InteractionCard.module.css';

const SOURCE_LABELS = {
  openfda_label: 'FDA Label',
  openfda_faers: 'FDA FAERS',
  twosides: 'TWOSIDES',
};

const AGREEMENT_LABELS = {
  agree:         { text: 'All sources agree',        cls: 'safe'    },
  disagree:      { text: 'Sources disagree',          cls: 'warning' },
  single_source: { text: 'Single source',             cls: 'neutral' },
  no_data:       { text: 'No data',                   cls: 'neutral' },
};

export default function InteractionCard({ interaction, compact }) {
  const [drugA, drugB] = interaction.drug_pair;
  const isMajor = interaction.severity === 'major' || interaction.severity === 'contraindicated';

  /* ── Compact (bottom strip) ── */
  if (compact) {
    return (
      <div className={`${styles.compact} ${isMajor ? styles.compactDanger : ''}`}>
        <div className={styles.compactHeader}>
          <span className={styles.compactName}>{cap(drugA)} + {cap(drugB)}</span>
          {isMajor
            ? <AlertCircle size={16} color="var(--color-red)" />
            : <CheckCircle size={16} color="var(--color-green)" />}
        </div>
        <span className={styles.compactLabel}>
          {isMajor ? 'Dangerous Combination' : 'This drug is a good match'}
        </span>
      </div>
    );
  }

  /* ── Full card ── */
  const agreement = AGREEMENT_LABELS[interaction.sources_agreement] ?? AGREEMENT_LABELS.no_data;
  const hasCitations = interaction.citations && interaction.citations.length > 0;

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={styles.pair}>{cap(drugA)} + {cap(drugB)}</div>
        <div className={styles.headerRight}>
          <span className={`badge badge-${agreement.cls}`}>{agreement.text}</span>
          <SeverityBadge severity={interaction.severity} />
        </div>
      </div>

      <p className={styles.headline}>{interaction.headline}</p>

      {interaction.reasoning && (
        <p className={styles.reasoning}>{interaction.reasoning}</p>
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
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function cap(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}
