import { useState, useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { supabase } from '../lib/supabase.js';
import { fetchProfile } from '../lib/db.js';
import { getSwapPresence } from '../lib/motion.js';
import styles from './SettingsPage.module.css';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { 'Authorization': `Bearer ${session.access_token}` } : {};
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [pat, setPat] = useState(null);
  const [patRevealed, setPatRevealed] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const swapPresence = getSwapPresence(reducedMotion, 10);

  useEffect(() => {
    fetchProfile()
      .then((p) => {
        if (!p) return;
        setProfile(p);
        if (p.pat) setPat(p.pat);
      })
      .finally(() => setLoadingProfile(false));
  }, []);

  async function generatePat() {
    setGenerating(true);
    try {
      const headers = await getAuthHeader();
      const res = await fetch(`${API}/api/tokens/generate`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const { token } = await res.json();
      setPat(token);
      setPatRevealed(true);
    } catch (e) {
      console.error('PAT generation failed', e);
    } finally {
      setGenerating(false);
    }
  }

  async function copyPat() {
    if (!pat) return;
    await navigator.clipboard.writeText(pat);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    navigate('/auth');
  }

  return (
    <div className={styles.page}>
      <div className={styles.logo}>Acuity</div>

      <button className={styles.back} onClick={() => navigate('/')}>
        <ArrowLeft size={14} />
        Back
      </button>

      <div className={styles.content}>
        <h1 className={styles.title}>Settings</h1>

        {/* NemoClaw Token */}
        <section className={styles.card}>
          <h2 className={styles.sectionTitle}>NemoClaw Token</h2>
          <p className={styles.sectionDesc}>
            Use this token to authenticate NemoClaw as you. Paste it into your NemoClaw tool configuration as the <code>X-API-Key</code> header.
          </p>

          <div className={styles.tokenSlot}>
            <AnimatePresence mode="wait">
              {loadingProfile ? (
                <motion.div
                  key="token-loading"
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  <div className={styles.loadingToken}>
                    <div className={`skeleton-block ${styles.loadingTokenValue}`} />
                    <div className={styles.loadingTokenActions}>
                      <div className={`skeleton-block ${styles.loadingTokenBtn}`} />
                      <div className={`skeleton-block ${styles.loadingTokenBtn}`} />
                    </div>
                  </div>
                </motion.div>
              ) : pat ? (
                <motion.div
                  key="token-loaded"
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  <div className={styles.tokenBox}>
                    <code className={styles.tokenValue}>
                      {patRevealed ? pat : `${pat.slice(0, 6)}${'•'.repeat(18)}`}
                    </code>
                    <div className={styles.tokenActions}>
                      <button className={styles.btn} onClick={() => setPatRevealed(r => !r)}>
                        {patRevealed ? 'Hide' : 'Reveal'}
                      </button>
                      <button className={styles.btn} onClick={copyPat}>
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.p
                  key="token-empty"
                  className={styles.noToken}
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  No token generated yet.
                </motion.p>
              )}
            </AnimatePresence>
          </div>

          <button className={styles.primaryBtn} onClick={generatePat} disabled={generating}>
            {generating ? 'Generating…' : pat ? 'Regenerate Token' : 'Generate Token'}
          </button>

          {pat && (
            <p className={styles.warning}>
              Regenerating will invalidate your current token immediately.
            </p>
          )}
        </section>

        {/* Account */}
        <section className={styles.card}>
          <h2 className={styles.sectionTitle}>Account</h2>
          <div className={styles.accountSlot}>
            <AnimatePresence mode="wait">
              {loadingProfile ? (
                <motion.div
                  key="account-loading"
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  <div className={`skeleton-block ${styles.loadingAccountName}`} />
                </motion.div>
              ) : profile ? (
                <motion.p
                  key="account-loaded"
                  className={styles.accountEmail}
                  initial={swapPresence.initial}
                  animate={swapPresence.animate}
                  exit={swapPresence.exit}
                >
                  {profile.name}
                </motion.p>
              ) : null}
            </AnimatePresence>
          </div>
          <button className={styles.dangerBtn} onClick={handleSignOut}>
            Sign out
          </button>
        </section>
      </div>
    </div>
  );
}
