import { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { getItemPresence, getSwapPresence, LAYOUT_TRANSITION } from '../lib/motion.js';
import { supabase } from '../lib/supabase.js';
import { updateProfileDoctor, addDrugToRegimen } from '../lib/db.js';
import { capitalize } from '../lib/utils.js';
import { streamAnalyzeOnboarding } from '../api/index.js';
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
  const reducedMotion = useReducedMotion();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

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
      navigate('/');
      return;
    }

    if (drugs.length < 2) {
      navigate('/');
      return;
    }

    // Step 3: run full-regimen analysis and navigate to the report
    setStep(3);
    try {
      await streamAnalyzeOnboarding(undefined, {
        onEvent({ type, data }) {
          if (type === 'rate_limit') {
            setRateLimited(true);
          } else if (type === 'report_done') {
            setRateLimited(false);
            navigate(`/session/${data.session_id}`);
          } else {
            setRateLimited(false);
          }
        },
        onError(err) {
          console.error('Onboarding analysis failed:', err);
          navigate('/');
        },
      });
    } catch (err) {
      console.error('Onboarding analysis failed:', err);
      navigate('/');
    }
  }
  const swapPresence = getSwapPresence(reducedMotion, 8);
  const itemPresence = getItemPresence(reducedMotion, 8, 0.99);

  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <div className={styles.logo}>Acuity</div>

        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div
              key="doctor-step"
              className={styles.stepContent}
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              <h1 className={styles.headline}>Tell us about your doctor</h1>
              <motion.form className={styles.card} onSubmit={handleDoctorContinue} layout transition={LAYOUT_TRANSITION}>
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
              </motion.form>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="medications-step"
              className={styles.stepContent}
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              <h1 className={styles.headline}>Let&apos;s add your current medications</h1>

              <motion.div className={styles.medCard} layout transition={LAYOUT_TRANSITION}>
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

                <AnimatePresence>
                  {drugs.length > 0 && (
                    <motion.div
                      key="drug-list"
                      className={styles.listWrap}
                      layout
                      transition={LAYOUT_TRANSITION}
                      initial={swapPresence.initial}
                      animate={swapPresence.animate}
                      exit={swapPresence.exit}
                    >
                      <p className={styles.listLabel}>You Added</p>
                      <AnimatePresence>
                        {drugs.map((drug, i) => (
                          <motion.div
                            key={drug.name.toLowerCase()}
                            className={styles.drugRow}
                            layout
                            transition={LAYOUT_TRANSITION}
                            initial={itemPresence.initial}
                            animate={itemPresence.animate}
                            exit={itemPresence.exit}
                          >
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
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>

              <div className={styles.actions}>
                <button className={styles.doneBtn} onClick={handleDone} disabled={loading}>
                  {loading ? 'Saving…' : 'Continue to Dashboard'}
                </button>
                <button className={styles.skipBtn} type="button" onClick={() => navigate('/')}>
                  Skip for now
                </button>
              </div>
            </motion.div>
          )}

          {step === 3 && (
            <motion.div
              key="analysis-step"
              className={styles.stepContent}
              initial={swapPresence.initial}
              animate={swapPresence.animate}
              exit={swapPresence.exit}
            >
              <h1 className={styles.headline}>Checking your medications…</h1>
              <p className={styles.loadingCopy}>
                Analyzing all interactions in your regimen. This takes a few seconds.
              </p>
              <AnimatePresence>
                {rateLimited && (
                  <motion.p
                    className={styles.rateLimitNote}
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.25 }}
                  >
                    This service is maintained for free — rate limits keep the AI model accessible to everyone. Hang tight while we wait for the next available slot.
                  </motion.p>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
