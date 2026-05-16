import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Edit2, Search, ChevronRight } from 'lucide-react';
import DrugRow from '../components/DrugRow.jsx';
import fixtures from '../data/fixtures.json';
import heroImg from '../../hero.jpg';
import styles from './HomePage.module.css';

const PROFILE = {
  name: 'Oleg Mrynskyi',
  age: 22,
  sex: 'Male',
  height: '194 cm',
  weight: '168 lb',
  doctor: 'Dr. Zhang',
  doctorEmail: 'zhang@stanfordhealth.org',
};

const REGIMEN = fixtures.regimen_report.regimen;
const PAST_REPORTS = fixtures.regimen_report.interactions;

export default function HomePage() {
  const [newDrug, setNewDrug] = useState('');
  const navigate = useNavigate();

  function handleCheck() {
    const trimmed = newDrug.trim();
    if (!trimmed) return;
    navigate('/session/pending', {
      state: {
        newDrug: trimmed,
        regimen: REGIMEN.map((d) => d.generic_name || d.input_name),
      },
    });
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleCheck();
  }

  return (
    <div
      className={styles.page}
      style={{ backgroundImage: `url(${heroImg})` }}
    >
      <div className={styles.logo}>Acuity</div>

      <div className={styles.content}>
        <h1 className={styles.greeting}>Hello, {PROFILE.name}</h1>

        <div className={styles.columns}>
          <div className={styles.left}>
            {/* My Medicine */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>My Medicine</span>
                <button className={styles.iconBtn} aria-label="Edit medicines">
                  <Edit2 size={15} />
                </button>
              </div>
              {REGIMEN.map((drug) => (
                <DrugRow key={drug.input_name} drug={drug} />
              ))}
            </div>

            {/* Taking something new */}
            <div className={styles.ctaCard}>
              <div className={styles.ctaTopRow}>
                <p className={styles.ctaLabel}>Taking something new?</p>
                <span className={`${styles.ctaLink} ${newDrug.trim() ? styles.ctaLinkActive : ''}`}>
                  Edit new medicine here <ChevronRight size={14} />
                </span>
              </div>
              <div className={styles.inputRow}>
                <input
                  className={styles.drugInput}
                  type="text"
                  placeholder="Enter medicine name"
                  value={newDrug}
                  onChange={(e) => setNewDrug(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                <button
                  className={styles.checkBtn}
                  onClick={handleCheck}
                  disabled={!newDrug.trim()}
                >
                  <Search size={15} />
                  Check
                </button>
              </div>
            </div>
          </div>

          {/* My Profile */}
          <div className={styles.right}>
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>My Profile</span>
                <button className={styles.iconBtn} aria-label="Edit profile">
                  <Edit2 size={15} />
                </button>
              </div>
              <dl className={styles.profileGrid}>
                <dt>Name</dt><dd>{PROFILE.name}</dd>
                <dt>Age</dt><dd>{PROFILE.age}</dd>
                <dt>Sex</dt><dd>{PROFILE.sex}</dd>
                <dt>Height</dt><dd>{PROFILE.height}</dd>
                <dt>Weight</dt><dd>{PROFILE.weight}</dd>
              </dl>
              <div className={styles.doctorSection}>
                <p className={styles.doctorLabel}>My Doctor</p>
                <p className={styles.doctorName}>{PROFILE.doctor}</p>
                <p className={styles.doctorEmail}>{PROFILE.doctorEmail}</p>
              </div>
            </div>
          </div>
        </div>

        {/* My Reports */}
        <section>
          <h2 className={styles.sectionTitle}>My Reports</h2>
          <div className={styles.reportList}>
            {PAST_REPORTS.map((interaction) => {
              const [drugA] = interaction.drug_pair;
              const isMajor =
                interaction.severity === 'major' ||
                interaction.severity === 'contraindicated';
              return (
                <div key={interaction.drug_pair.join('-')} className={styles.reportCard}>
                  <div className={styles.reportCardTop}>
                    <span className={styles.reportDrug}>{capitalize(drugA)}</span>
                    <span className={styles.reportDate}>3 days ago</span>
                  </div>
                  <div className={styles.reportStatus}>
                    <span className={`${styles.reportDot} ${isMajor ? styles.reportDotDanger : styles.reportDotSafe}`} />
                    <span className={`${styles.reportStatusLabel} ${isMajor ? styles.reportStatusDanger : styles.reportStatusSafe}`}>
                      {isMajor ? 'Dangerous Combination' : 'Good match'}
                    </span>
                  </div>
                  <p className={styles.reportHeadline}>{interaction.headline}</p>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
