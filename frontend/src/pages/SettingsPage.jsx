import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { supabase } from '../lib/supabase.js';
import { fetchProfile } from '../lib/db.js';
import heroImg from '../../hero.jpg';
import styles from './SettingsPage.module.css';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { 'Authorization': `Bearer ${session.access_token}` } : {};
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [pat, setPat] = useState(null);
  const [patRevealed, setPatRevealed] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchProfile().then((p) => {
      if (!p) return;
      setProfile(p);
      if (p.pat) setPat(p.pat);
    });
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
    <div className={styles.page} style={{ backgroundImage: `url(${heroImg})` }}>
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

          {pat ? (
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
          ) : (
            <p className={styles.noToken}>No token generated yet.</p>
          )}

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
          {profile && (
            <p className={styles.accountEmail}>{profile.name}</p>
          )}
          <button className={styles.dangerBtn} onClick={handleSignOut}>
            Sign out
          </button>
        </section>
      </div>
    </div>
  );
}
