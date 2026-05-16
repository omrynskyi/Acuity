import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Edit2, Search, ChevronRight, Trash2, Settings } from 'lucide-react';
import DrugRow from '../components/DrugRow.jsx';
import CustomSelect from '../components/CustomSelect.jsx';
import { fetchProfile, fetchRegimen, fetchRecentSessions, updateProfile, updateRegimenDrug, addDrugToRegimen, removeDrugFromRegimen } from '../lib/db.js';
import { supabase } from '../lib/supabase.js';
import styles from './HomePage.module.css';

const FREQ_OPTIONS = ['daily', 'twice daily', 'weekly', 'custom'];

async function fetchDrugSuggestions(term) {
  if (!term || term.length < 2) return [];
  const url = `https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search?terms=${encodeURIComponent(term)}&ef=STRENGTHS_AND_FORMS`;
  const res = await fetch(url);
  const [, names] = await res.json();
  return names || [];
}

export default function HomePage() {
  const navigate = useNavigate();
  const [newDrug, setNewDrug] = useState('');
  const [newDrugSuggestions, setNewDrugSuggestions] = useState([]);
  const [profile, setProfile] = useState(null);
  const [regimen, setRegimen] = useState([]);
  const [pastSessions, setPastSessions] = useState([]);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Medicine edit modal
  const [medOpen, setMedOpen] = useState(false);
  const [medList, setMedList] = useState([]); // working copy
  const [medQuery, setMedQuery] = useState('');
  const [medSuggestions, setMedSuggestions] = useState([]);
  const [medSaving, setMedSaving] = useState(false);
  const suggestRef = useRef(null);
  const newDrugSuggestRef = useRef(null);

  function loadData() {
    fetchProfile()
      .then((p) => {
        if (!p) return;
        setProfile(p);
        return Promise.all([
          fetchRegimen(p.id).then(setRegimen),
          fetchRecentSessions(p.id).then(setPastSessions),
        ]);
      })
      .catch(console.error);
  }

  useEffect(() => {
    loadData();
    // Re-fetch when auth state settles (covers the case where session propagates after mount)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(() => loadData());
    return () => subscription.unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Medicine modal ──────────────────────────────────────────────────────────

  function openMedModal() {
    setMedList(regimen.map(d => ({ ...d, _new: false })));
    setMedQuery('');
    setMedSuggestions([]);
    setMedOpen(true);
  }

  useEffect(() => {
    if (!medQuery.trim()) { setMedSuggestions([]); return; }
    const t = setTimeout(() =>
      fetchDrugSuggestions(medQuery).then(setMedSuggestions).catch(() => setMedSuggestions([])),
      250
    );
    return () => clearTimeout(t);
  }, [medQuery]);

  // ── New Drug Autocomplete ──────────────────────────────────────────────────

  useEffect(() => {
    if (!newDrug.trim()) { setNewDrugSuggestions([]); return; }
    const t = setTimeout(() =>
      fetchDrugSuggestions(newDrug).then(setNewDrugSuggestions).catch(() => setNewDrugSuggestions([])),
      250
    );
    return () => clearTimeout(t);
  }, [newDrug]);

  useEffect(() => {
    function onDown(e) {
      if (suggestRef.current && !suggestRef.current.contains(e.target)) setMedSuggestions([]);
      if (newDrugSuggestRef.current && !newDrugSuggestRef.current.contains(e.target)) setNewDrugSuggestions([]);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  function selectNewDrug(name) {
    setNewDrug(name);
    setNewDrugSuggestions([]);
  }

  function addMedEntry(name) {
    if (!medList.find(d => d.input_name === name.toLowerCase())) {
      setMedList(prev => [...prev, { input_name: name.toLowerCase(), generic_name: name.toLowerCase(), dose: '', frequency: 'daily', _new: true }]);
    }
    setMedQuery('');
    setMedSuggestions([]);
  }

  function updateMedField(idx, field, value) {
    setMedList(prev => prev.map((d, i) => i === idx ? { ...d, [field]: value } : d));
  }

  function removeMedEntry(idx) {
    setMedList(prev => prev.filter((_, i) => i !== idx));
  }

  async function saveMeds() {
    setMedSaving(true);
    try {
      // Remove entries that were deleted
      const removedIds = regimen
        .filter(r => !medList.find(m => m.id === r.id))
        .map(r => r.id);
      await Promise.all(removedIds.map(id => removeDrugFromRegimen(id)));

      // Update existing entries
      await Promise.all(
        medList
          .filter(m => !m._new)
          .map(m => updateRegimenDrug(m.id, { dose: m.dose, frequency: m.frequency }))
      );

      // Insert new entries
      const newEntries = medList.filter(m => m._new);
      await Promise.all(
        newEntries.map((m, i) =>
          addDrugToRegimen(profile.id, {
            input_name: m.input_name,
            generic_name: m.generic_name,
            dose: m.dose || null,
            frequency: m.frequency,
            sort_order: regimen.length + i,
          })
        )
      );

      // Refresh regimen from DB
      const fresh = await fetchRegimen(profile.id);
      setRegimen(fresh);
      setMedOpen(false);
    } catch (err) {
      console.error(err);
    } finally {
      setMedSaving(false);
    }
  }

  // ── Profile modal ───────────────────────────────────────────────────────────

  function openEdit() {
    setEditForm({
      name: profile.name ?? '',
      age: profile.age ?? '',
      sex: profile.sex ?? '',
      height: profile.height ?? '',
      weight: profile.weight ?? '',
      doctor: profile.doctor ?? '',
      doctor_email: profile.doctor_email ?? '',
    });
    setEditOpen(true);
  }

  async function saveEdit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProfile(profile.id, {
        name: editForm.name,
        age: editForm.age ? parseInt(editForm.age) : null,
        sex: editForm.sex,
        height: editForm.height,
        weight: editForm.weight,
        doctor: editForm.doctor,
        doctor_email: editForm.doctor_email,
      });
      setProfile((p) => ({ ...p, ...editForm, age: editForm.age ? parseInt(editForm.age) : p.age }));
      setEditOpen(false);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  function handleCheck() {
    const trimmed = newDrug.trim();
    if (!trimmed) return;
    navigate('/session/pending', {
      state: {
        newDrug: trimmed,
        regimen: regimen.map((d) => d.generic_name || d.input_name),
        profileId: profile?.id,
        doctor: profile?.doctor,
        doctorEmail: profile?.doctor_email,
      },
    });
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      if (newDrugSuggestions.length > 0) {
        selectNewDrug(newDrugSuggestions[0]);
      } else {
        handleCheck();
      }
    }
  }

  if (!profile) return (
    <div className={styles.page}>
      <div className={styles.logo}>Acuity</div>
    </div>
  );

  return (
    <div className={styles.page}>
      <div className={styles.logo}>Acuity</div>
      <button
        onClick={() => navigate('/settings')}
        style={{ position: 'absolute', top: 20, right: 28, background: 'none', border: 'none', cursor: 'pointer', opacity: 0.6, zIndex: 2, display: 'flex', alignItems: 'center' }}
        aria-label="Settings"
      >
        <Settings size={18} />
      </button>

      <div className={styles.content}>
        <h1 className={styles.greeting}>Hello, {profile.name}</h1>

        <div className={styles.columns}>
          <div className={styles.left}>
            {/* My Medicine */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>My Medicine</span>
                <button className={styles.iconBtn} aria-label="Edit medicines" onClick={openMedModal}>
                  <Edit2 size={15} />
                </button>
              </div>
              {regimen.map((drug) => (
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
                <div className={styles.newDrugSearchWrap} ref={newDrugSuggestRef}>
                  <input
                    className={styles.drugInput}
                    type="text"
                    placeholder="Enter medicine name"
                    value={newDrug}
                    onChange={(e) => setNewDrug(e.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="off"
                  />
                  {newDrugSuggestions.length > 0 && (
                    <ul className={styles.newDrugSuggestList}>
                      {newDrugSuggestions.slice(0, 6).map(name => (
                        <li key={name} className={styles.newDrugSuggestItem} onMouseDown={() => selectNewDrug(name)}>
                          {name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
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
                <button className={styles.iconBtn} aria-label="Edit profile" onClick={openEdit}>
                  <Edit2 size={15} />
                </button>
              </div>
              <dl className={styles.profileGrid}>
                <dt>Name</dt><dd>{profile.name}</dd>
                <dt>Age</dt><dd>{profile.age}</dd>
                <dt>Sex</dt><dd>{profile.sex}</dd>
                <dt>Height</dt><dd>{profile.height}</dd>
                <dt>Weight</dt><dd>{profile.weight}</dd>
              </dl>
              <div className={styles.doctorSection}>
                <p className={styles.doctorLabel}>My Doctor</p>
                <p className={styles.doctorName}>{profile.doctor}</p>
                <p className={styles.doctorEmail}>{profile.doctor_email}</p>
              </div>
            </div>
          </div>
        </div>

        {/* My Reports */}
        <section>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>My Reports</h2>
            <button className={styles.viewAllBtn} onClick={() => navigate('/reports')}>
              View All <ChevronRight size={14} />
            </button>
          </div>
          <div className={styles.reportList}>
            {pastSessions.map((session) => {
              const isMajor =
                session.overall_severity === 'major' ||
                session.overall_severity === 'contraindicated';
              return (
                <div
                  key={session.id}
                  className={styles.reportCard}
                  onClick={() => navigate(`/session/${session.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className={styles.reportCardTop}>
                    <span className={styles.reportDrug}>{capitalize(session.new_drug)}</span>
                    <span className={styles.reportDate}>{formatDate(session.generated_at)}</span>
                  </div>
                  <div className={styles.reportStatus}>
                    <span className={`${styles.reportDot} ${isMajor ? styles.reportDotDanger : styles.reportDotSafe}`} />
                    <span className={`${styles.reportStatusLabel} ${isMajor ? styles.reportStatusDanger : styles.reportStatusSafe}`}>
                      {isMajor ? 'Dangerous Combination' : 'Good match'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {medOpen && (
        <div className={styles.modalOverlay} onClick={() => setMedOpen(false)}>
          <div className={styles.modalCard} onClick={e => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <h2 className={styles.modalTitle}>My Medicine</h2>

            {/* Search */}
            <div className={styles.medSearchWrap} ref={suggestRef}>
              <input
                className={styles.medSearchInput}
                placeholder="Add a medicine…"
                value={medQuery}
                onChange={e => setMedQuery(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (medSuggestions.length > 0) addMedEntry(medSuggestions[0]);
                    else if (medQuery.trim()) addMedEntry(medQuery.trim());
                  }
                }}
                autoComplete="off"
              />
              {medSuggestions.length > 0 && (
                <ul className={styles.medSuggestList}>
                  {medSuggestions.slice(0, 6).map(name => (
                    <li key={name} className={styles.medSuggestItem} onMouseDown={() => addMedEntry(name)}>
                      {name}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Drug list */}
            <div className={styles.medEditList}>
              {medList.map((drug, i) => (
                <div key={drug.id ?? drug.input_name} className={styles.medEditRow}>
                  <span className={styles.medEditName}>{capitalize(drug.generic_name || drug.input_name)}</span>

                  <input
                    className={styles.medEditDose}
                    placeholder="Dose"
                    value={drug.dose ?? ''}
                    onChange={e => updateMedField(i, 'dose', e.target.value)}
                  />

                  {drug.frequency === 'custom' ? (
                    <input
                      className={styles.freqCustomInput}
                      placeholder="e.g. every 3 days"
                      value={drug.custom_frequency ?? ''}
                      onChange={e => updateMedField(i, 'custom_frequency', e.target.value)}
                      onBlur={e => { if (!e.target.value.trim()) updateMedField(i, 'frequency', 'daily'); }}
                      autoFocus
                    />
                  ) : (
                    <CustomSelect
                      compact
                      value={drug.frequency ?? 'daily'}
                      onChange={v => updateMedField(i, 'frequency', v)}
                      options={FREQ_OPTIONS.map(f => ({ value: f, label: f }))}
                    />
                  )}

                  <button
                    type="button"
                    className={styles.medRemoveBtn}
                    onClick={() => removeMedEntry(i)}
                    aria-label="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              {medList.length === 0 && (
                <p className={styles.medEmpty}>No medicines added yet.</p>
              )}
            </div>

            <div className={styles.modalActions}>
              <button type="button" className={styles.modalCancelBtn} onClick={() => setMedOpen(false)}>Cancel</button>
              <button type="button" className={styles.modalSaveBtn} onClick={saveMeds} disabled={medSaving}>
                {medSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {editOpen && (
        <div className={styles.modalOverlay} onClick={() => setEditOpen(false)}>
          <form
            className={styles.modalCard}
            onClick={(e) => e.stopPropagation()}
            onSubmit={saveEdit}
          >
            <h2 className={styles.modalTitle}>Edit Profile</h2>

            <div className={styles.modalGrid}>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Name</label>
                <input className={styles.modalInput} value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Age</label>
                <input className={styles.modalInput} type="number" min="0" value={editForm.age} onChange={e => setEditForm(f => ({ ...f, age: e.target.value }))} />
              </div>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Sex</label>
                <input className={styles.modalInput} value={editForm.sex} onChange={e => setEditForm(f => ({ ...f, sex: e.target.value }))} />
              </div>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Height</label>
                <input className={styles.modalInput} placeholder="e.g. 5 ft 10 in" value={editForm.height} onChange={e => setEditForm(f => ({ ...f, height: e.target.value }))} />
              </div>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Weight</label>
                <input className={styles.modalInput} placeholder="e.g. 165 lb" value={editForm.weight} onChange={e => setEditForm(f => ({ ...f, weight: e.target.value }))} />
              </div>
              <div className={styles.modalField}>
                <label className={styles.modalLabel}>Doctor</label>
                <input className={styles.modalInput} value={editForm.doctor} onChange={e => setEditForm(f => ({ ...f, doctor: e.target.value }))} />
              </div>
              <div className={`${styles.modalField} ${styles.modalFieldFull}`}>
                <label className={styles.modalLabel}>Doctor email</label>
                <input className={styles.modalInput} type="email" value={editForm.doctor_email} onChange={e => setEditForm(f => ({ ...f, doctor_email: e.target.value }))} />
              </div>
            </div>

            <div className={styles.modalActions}>
              <button type="button" className={styles.modalCancelBtn} onClick={() => setEditOpen(false)}>Cancel</button>
              <button type="submit" className={styles.modalSaveBtn} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  return d.toLocaleDateString();
}
