import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { supabase } from '../lib/supabase.js';
import { updateProfileDoctor, addDrugToRegimen } from '../lib/db.js';
import styles from './OnboardingPage.module.css';

async function fetchSuggestions(term) {
  if (!term || term.length < 2) return [];
  const url = `https://clinicaltables.nlm.nih.gov/api/rxterms/v3/search?terms=${encodeURIComponent(term)}&ef=STRENGTHS_AND_FORMS`;
  const res = await fetch(url);
  const [, names] = await res.json();
  return names || [];
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // Step 1 — doctor info
  const [doctor, setDoctor] = useState('');
  const [doctorEmail, setDoctorEmail] = useState('');

  // Step 2 — medications
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [drugs, setDrugs] = useState([]);
  const suggestRef = useRef(null);

  // Debounced autocomplete
  useEffect(() => {
    if (!query.trim()) { setSuggestions([]); return; }
    const timer = setTimeout(() => {
      fetchSuggestions(query).then(setSuggestions).catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Close suggestions on outside click
  useEffect(() => {
    function onDown(e) {
      if (suggestRef.current && !suggestRef.current.contains(e.target)) setSuggestions([]);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  function addDrug(name) {
    if (!drugs.find(d => d.name.toLowerCase() === name.toLowerCase())) {
      setDrugs(prev => [...prev, { name, dose: '' }]);
    }
    setQuery('');
    setSuggestions([]);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (suggestions.length > 0) { addDrug(suggestions[0]); }
      else if (query.trim()) { addDrug(query.trim()); }
    }
  }

  function updateDose(index, dose) {
    setDrugs(prev => prev.map((d, i) => i === index ? { ...d, dose } : d));
  }

  function removeDrug(index) {
    setDrugs(prev => prev.filter((_, i) => i !== index));
  }

  async function handleDoctorContinue(e) {
    e.preventDefault();
    setLoading(true);
    try {
      if (doctor.trim()) {
        const { data: profile } = await supabase.from('profiles').select('id').maybeSingle();
        if (profile?.id) await updateProfileDoctor(profile.id, doctor.trim(), doctorEmail.trim());
      }
    } catch (err) {
      console.error('Failed to save doctor info:', err);
    } finally {
      setLoading(false);
      setStep(2);
    }
  }

  async function handleDone() {
    setLoading(true);
    try {
      const { data: profile } = await supabase.from('profiles').select('id').maybeSingle();
      const profileId = profile?.id;
      if (profileId && drugs.length > 0) {
        await Promise.all(
          drugs.map((d, i) =>
            addDrugToRegimen(profileId, {
              input_name: d.name.toLowerCase(),
              generic_name: d.name.toLowerCase(),
              dose: d.dose || null,
              sort_order: i,
            })
          )
        );
      }
    } catch (err) {
      console.error('Failed to save medications:', err);
    } finally {
      navigate('/');
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.logo}>Acuity</div>

      {step === 1 && (
        <>
          <h1 className={styles.headline}>Tell us about your doctor</h1>
          <form className={styles.card} onSubmit={handleDoctorContinue}>
            <div className={styles.field}>
              <label className={styles.label}>Doctor&apos;s name</label>
              <input
                className={styles.input}
                placeholder="Dr. Smith"
                value={doctor}
                onChange={e => setDoctor(e.target.value)}
                autoFocus
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Doctor&apos;s email</label>
              <input
                className={styles.input}
                placeholder="doctor@clinic.com"
                type="email"
                value={doctorEmail}
                onChange={e => setDoctorEmail(e.target.value)}
              />
            </div>
            <button type="submit" className={styles.doneBtn} disabled={loading}>
              {loading ? 'Saving…' : 'Continue'}
            </button>
            <button type="button" className={styles.skipBtn} onClick={() => setStep(2)}>
              Skip for now
            </button>
          </form>
        </>
      )}

      {step === 2 && (
        <>
          <h1 className={styles.headline}>Let&apos;s add your current medications</h1>

          <div className={styles.medCard}>
            {/* Search with autocomplete */}
            <div className={styles.searchWrap} ref={suggestRef}>
              <input
                className={styles.searchInput}
                placeholder="Start Typing"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                autoFocus
                autoComplete="off"
              />
              {suggestions.length > 0 && (
                <ul className={styles.suggestionList}>
                  {suggestions.slice(0, 6).map(name => (
                    <li
                      key={name}
                      className={styles.suggestionItem}
                      onMouseDown={() => addDrug(name)}
                    >
                      {name}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Added drugs */}
            {drugs.length > 0 && (
              <div className={styles.listWrap}>
                <p className={styles.listLabel}>You Added</p>
                {drugs.map((drug, i) => (
                  <div key={i} className={styles.drugRow}>
                    <span className={styles.drugName}>{capitalize(drug.name)}</span>
                    <input
                      className={styles.doseInput}
                      placeholder="Dose"
                      value={drug.dose}
                      onChange={e => updateDose(i, e.target.value)}
                    />
                    <button className={styles.removeBtn} type="button" onClick={() => removeDrug(i)} aria-label="Remove">
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className={styles.actions}>
            <button className={styles.doneBtn} onClick={handleDone} disabled={loading}>
              {loading ? 'Saving…' : 'Continue to Dashboard'}
            </button>
            <button className={styles.skipBtn} type="button" onClick={() => navigate('/')}>
              Skip for now
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}
