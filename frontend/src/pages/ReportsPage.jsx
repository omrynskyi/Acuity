import { useState, useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { capitalize } from '../lib/utils.js';
import { ChevronLeft, Search, Archive, ArchiveRestore, Trash2 } from 'lucide-react';
import CustomSelect from '../components/CustomSelect.jsx';
import { getSwapPresence } from '../lib/motion.js';
import {
  fetchProfile,
  fetchAllSessions,
  fetchArchivedSessions,
  archiveSession,
  unarchiveSession,
  deleteSession,
  deleteSessions,
  unarchiveSessions,
} from '../lib/db.js';
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
  const reducedMotion = useReducedMotion();
  const [profile, setProfile] = useState(null);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('active');

  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');

  // Selection state (archived tab only)
  const [selected, setSelected] = useState(new Set());

  function loadReports(p, currentTab) {
    const fetcher = currentTab === 'archived' ? fetchArchivedSessions : fetchAllSessions;
    fetcher(p.id).then(data => {
      setReports(data || []);
      setSelected(new Set());
      setLoading(false);
    });
  }

  useEffect(() => {
    fetchProfile().then(p => {
      if (!p) { navigate('/auth'); return; }
      setProfile(p);
      loadReports(p, tab);
    });
  }, [navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  function switchTab(next) {
    setTab(next);
    setSearch('');
    setSeverityFilter('all');
    setSelected(new Set());
    setLoading(true);
    loadReports(profile, next);
  }

  async function handleArchive(e, sessionId) {
    e.stopPropagation();
    await archiveSession(sessionId);
    setReports(prev => prev.filter(r => r.id !== sessionId));
  }

  async function handleUnarchive(e, sessionId) {
    e.stopPropagation();
    await unarchiveSession(sessionId);
    setReports(prev => prev.filter(r => r.id !== sessionId));
    setSelected(prev => { const s = new Set(prev); s.delete(sessionId); return s; });
  }

  async function handleDelete(e, sessionId) {
    e.stopPropagation();
    await deleteSession(sessionId);
    setReports(prev => prev.filter(r => r.id !== sessionId));
    setSelected(prev => { const s = new Set(prev); s.delete(sessionId); return s; });
  }

  function toggleSelect(e, id) {
    e.stopPropagation();
    setSelected(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  }

  function toggleSelectAll() {
    if (selected.size === filteredReports.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filteredReports.map(r => r.id)));
    }
  }

  async function handleBulkRestore() {
    const ids = [...selected];
    await unarchiveSessions(ids);
    setReports(prev => prev.filter(r => !selected.has(r.id)));
    setSelected(new Set());
  }

  async function handleBulkDelete() {
    const ids = [...selected];
    await deleteSessions(ids);
    setReports(prev => prev.filter(r => !selected.has(r.id)));
    setSelected(new Set());
  }

  async function handleDeleteAll() {
    const ids = filteredReports.map(r => r.id);
    await deleteSessions(ids);
    setReports(prev => prev.filter(r => !ids.includes(r.id)));
    setSelected(new Set());
  }

  async function handleRestoreAll() {
    const ids = filteredReports.map(r => r.id);
    await unarchiveSessions(ids);
    setReports(prev => prev.filter(r => !ids.includes(r.id)));
    setSelected(new Set());
  }

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

  const allSelected = filteredReports.length > 0 && selected.size === filteredReports.length;
  const someSelected = selected.size > 0;
  const swapPresence = getSwapPresence(reducedMotion, 8);

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <button onClick={() => navigate('/')} className={styles.backBtn}>
            <ChevronLeft size={20} />
            Back to Dashboard
          </button>
          <h1 className={styles.title}>All Interaction Reports</h1>
        </header>

        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === 'active' ? styles.tabActive : ''}`}
            onClick={() => switchTab('active')}
          >
            Reports
          </button>
          <button
            className={`${styles.tab} ${tab === 'archived' ? styles.tabActive : ''}`}
            onClick={() => switchTab('archived')}
          >
            <Archive size={13} /> Archived
          </button>
        </div>

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

        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={swapPresence.initial}
            animate={swapPresence.animate}
            exit={swapPresence.exit}
          >
            <AnimatePresence>
              {tab === 'archived' && filteredReports.length > 0 && (
                <div
                  key="bulk-bar"
                  className={styles.bulkBar}
                >
                  <label className={styles.selectAllLabel} onClick={toggleSelectAll}>
                    <span className={`${styles.checkbox} ${allSelected ? styles.checkboxChecked : ''}`} />
                    {allSelected ? 'Deselect all' : 'Select all'}
                  </label>

                  {someSelected && (
                    <div className={styles.bulkActions}>
                      <span className={styles.bulkCount}>{selected.size} selected</span>
                      <button className={styles.bulkBtn} onClick={handleBulkRestore}>
                        <ArchiveRestore size={14} /> Restore
                      </button>
                      <button className={`${styles.bulkBtn} ${styles.bulkBtnDanger}`} onClick={handleBulkDelete}>
                        <Trash2 size={14} /> Delete
                      </button>
                    </div>
                  )}

                  {!someSelected && (
                    <div className={styles.bulkActions}>
                      <button className={styles.bulkBtn} onClick={handleRestoreAll}>
                        <ArchiveRestore size={14} /> Restore all
                      </button>
                      <button className={`${styles.bulkBtn} ${styles.bulkBtnDanger}`} onClick={handleDeleteAll}>
                        <Trash2 size={14} /> Delete all
                      </button>
                    </div>
                  )}
                </div>
              )}
            </AnimatePresence>

            <AnimatePresence mode="wait">
              {loading ? (
                <motion.div
                  key={`loading-${tab}`}
                  className={`${styles.gridSwap} ${styles.loaderSwap}`}
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  <div className={styles.loadingStage}>
                    <div className="app-loader">
                      <div className="app-loader-mark" aria-hidden="true">
                        <div className="app-loader-ring" />
                        <div className="app-loader-core" />
                      </div>
                      <div className="app-loader-copy">
                        <p className="app-loader-title">
                          {tab === 'archived' ? 'Loading archived reports' : 'Loading your reports'}
                        </p>
                        <p className="app-loader-subtitle">
                          Preparing the full report list before showing it all at once.
                        </p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key={`loaded-${tab}`}
                  className={styles.gridSwap}
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  <div className={styles.grid}>
                    {filteredReports.map(session => {
                      const isMajor = session.overall_severity === 'major' || session.overall_severity === 'contraindicated';
                      const isSelected = selected.has(session.id);
                      return (
                        <div
                          key={session.id}
                          className={`${styles.reportCard} ${isSelected ? styles.reportCardSelected : ''}`}
                          onClick={() => tab === 'active' ? navigate(`/session/${session.id}`) : null}
                        >
                          <div className={styles.cardTop}>
                            <div className={styles.cardTopLeft}>
                              {tab === 'archived' && (
                                <span
                                  className={`${styles.checkbox} ${isSelected ? styles.checkboxChecked : ''}`}
                                  onClick={e => toggleSelect(e, session.id)}
                                />
                              )}
                              <span
                                className={styles.drugName}
                                onClick={() => navigate(`/session/${session.id}`)}
                                style={tab === 'archived' ? { cursor: 'pointer' } : {}}
                              >
                                {capitalize(session.new_drug)}
                              </span>
                            </div>
                            <div className={styles.cardTopRight}>
                              <span className={styles.date}>{formatDate(session.generated_at)}</span>
                              {tab === 'active' ? (
                                <button
                                  className={styles.archiveBtn}
                                  onClick={e => handleArchive(e, session.id)}
                                  title="Archive"
                                >
                                  <Archive size={14} />
                                </button>
                              ) : (
                                <div className={styles.archivedCardActions}>
                                  <button
                                    className={styles.archiveBtn}
                                    onClick={e => handleUnarchive(e, session.id)}
                                    title="Restore"
                                  >
                                    <ArchiveRestore size={14} />
                                  </button>
                                  <button
                                    className={`${styles.archiveBtn} ${styles.deleteBtn}`}
                                    onClick={e => handleDelete(e, session.id)}
                                    title="Delete permanently"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              )}
                            </div>
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
                      <p className={styles.empty}>
                        {tab === 'archived' ? 'No archived reports.' : 'No reports found matching your criteria.'}
                      </p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
