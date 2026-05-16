import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Search, Filter } from 'lucide-react';
import CustomSelect from '../components/CustomSelect.jsx';
import { fetchProfile, fetchAllSessions } from '../lib/db.js';
import heroImg from '../../hero.jpg';
import styles from './ReportsPage.module.css';

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All Severities' },
  { value: 'dangerous', label: 'Dangerous Only' },
  { value: 'safe', label: 'Safe Only' },
];

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'alphabetical', label: 'A-Z' },
];

export default function ReportsPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filtering states
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');

  useEffect(() => {
    fetchProfile().then(p => {
      if (!p) {
        navigate('/auth');
        return;
      }
      setProfile(p);
      fetchAllSessions(p.id).then(data => {
        setReports(data || []);
        setLoading(false);
      });
    });
  }, [navigate]);

  const filteredReports = reports
    .filter(r => {
      const matchesSearch = r.new_drug.toLowerCase().includes(search.toLowerCase());
      const isMajor = r.overall_severity === 'major' || r.overall_severity === 'contraindicated';
      const matchesSeverity = severityFilter === 'all' || 
        (severityFilter === 'dangerous' && isMajor) || 
        (severityFilter === 'safe' && !isMajor);
      return matchesSearch && matchesSeverity;
    })
    .sort((a, b) => {
      if (sortBy === 'newest') return new Date(b.generated_at) - new Date(a.generated_at);
      if (sortBy === 'oldest') return new Date(a.generated_at) - new Date(b.generated_at);
      if (sortBy === 'alphabetical') return a.new_drug.localeCompare(b.new_drug);
      return 0;
    });

  if (loading) return <div className={styles.loading}>Loading reports...</div>;

  return (
    <div className={styles.page} style={{ backgroundImage: `url(${heroImg})` }}>
      <div className={styles.container}>
        <header className={styles.header}>
          <button onClick={() => navigate('/')} className={styles.backBtn}>
            <ChevronLeft size={20} />
            Back to Dashboard
          </button>
          <h1 className={styles.title}>All Interaction Reports</h1>
        </header>

        <div className={styles.controls}>
          <div className={styles.searchBox}>
            <Search size={18} className={styles.searchIcon} />
            <input 
              type="text" 
              placeholder="Search by medicine name..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              className={styles.searchInput}
            />
          </div>
          
          <div className={styles.filters}>
            <div className={styles.filterGroup}>
              <Filter size={16} />
              <CustomSelect
                value={severityFilter}
                onChange={setSeverityFilter}
                options={SEVERITY_OPTIONS}
              />
            </div>

            <CustomSelect
              value={sortBy}
              onChange={setSortBy}
              options={SORT_OPTIONS}
            />
          </div>
        </div>

        <div className={styles.grid}>
          {filteredReports.map(session => {
            const isMajor = session.overall_severity === 'major' || session.overall_severity === 'contraindicated';
            return (
              <div 
                key={session.id} 
                className={styles.reportCard}
                onClick={() => navigate(`/session/${session.id}`)}
              >
                <div className={styles.cardTop}>
                  <span className={styles.drugName}>{capitalize(session.new_drug)}</span>
                  <span className={styles.date}>{formatDate(session.generated_at)}</span>
                </div>
                <div className={styles.status}>
                  <span className={`${styles.dot} ${isMajor ? styles.dotDanger : styles.dotSafe}`} />
                  <span className={`${styles.statusLabel} ${isMajor ? styles.statusDanger : styles.statusSafe}`}>
                    {isMajor ? 'Dangerous Combination' : 'Good match'}
                  </span>
                </div>
              </div>
            );
          })}
          {filteredReports.length === 0 && (
            <p className={styles.empty}>No reports found matching your criteria.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined, { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
}
