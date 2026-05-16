import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CustomSelect from '../components/CustomSelect.jsx';
import { supabase } from '../lib/supabase.js';
import styles from './AuthPage.module.css';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

async function createProfileViaBackend(userId, { name, age, sex, height, weight }) {
  const res = await fetch(`${BASE}/api/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, name, age, sex, height, weight }),
  });
  if (!res.ok) throw new Error(`Profile creation failed: ${res.status}`);
  return res.json();
}

const GENDER_OPTIONS = [
  { value: 'Male', label: 'Male' },
  { value: 'Female', label: 'Female' },
  { value: 'Non-binary', label: 'Non-binary' },
  { value: 'Prefer not to say', label: 'Prefer not to say' },
];

const GOOGLE_LOGO = (
  <svg className={styles.googleLogo} viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
    <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
    <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
    <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.548 0 9s.348 2.825.957 4.039l3.007-2.332z"/>
    <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
  </svg>
);

export default function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('signup'); // 'signup' | 'signin'
  const [step, setStep] = useState(1); // signup steps 1 or 2
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Step 1 fields
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [sex, setSex] = useState('');
  const [heightFt, setHeightFt] = useState('');
  const [heightIn, setHeightIn] = useState('');
  const [weight, setWeight] = useState('');

  // Step 2 / sign-in fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  function switchMode(m) {
    setMode(m);
    setStep(1);
    setError('');
  }

  function handleContinue(e) {
    e.preventDefault();
    if (!name || !age) { setError('Please fill in your name and age.'); return; }
    setError('');
    setStep(2);
  }

  async function handleSignUp(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data, error: authErr } = await supabase.auth.signUp({ email, password });
      if (authErr) throw authErr;
      const user = data.user;
      if (user) {
        const height = heightFt ? `${heightFt} ft${heightIn ? ` ${heightIn} in` : ''}` : '';
        await createProfileViaBackend(user.id, { name, age: parseInt(age), sex, height, weight: weight ? `${weight} lb` : '' });
      }
      navigate('/onboarding');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSignIn(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { error: authErr } = await supabase.auth.signInWithPassword({ email, password });
      if (authErr) throw authErr;
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/` },
    });
  }

  return (
    <div className={styles.page}>
      <div className={styles.logo}>Acuity</div>
      <h1 className={styles.headline}>
        Start knowing your <strong>medicine</strong>
      </h1>


      <div className={styles.card}>
        {mode === 'signup' && step === 1 && (
          <form onSubmit={handleContinue}>
            <p className={styles.cardTitle}>First we need some info</p>

            <div className={styles.field}>
              <label className={styles.label}>What&apos;s your name?</label>
              <input className={styles.input} placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>How old are you?</label>
              <input className={styles.input} placeholder="Age" type="number" value={age} onChange={e => setAge(e.target.value)} />
            </div>

            <div className={styles.row}>
              <div className={styles.field}>
                <label className={styles.label}>What&apos;s your gender?</label>
                <CustomSelect
                  value={sex}
                  onChange={setSex}
                  options={GENDER_OPTIONS}
                  placeholder="Select"
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>How tall are you?</label>
                <div className={styles.heightWrap}>
                  <input
                    className={styles.heightInput}
                    placeholder="0"
                    type="number"
                    min="0"
                    value={heightFt}
                    onChange={e => setHeightFt(e.target.value)}
                  />
                  <span className={styles.heightUnit}>ft</span>
                  <input
                    className={styles.heightInput}
                    placeholder="0"
                    type="number"
                    min="0"
                    max="11"
                    value={heightIn}
                    onChange={e => setHeightIn(e.target.value)}
                  />
                  <span className={styles.heightUnit}>in</span>
                </div>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>What&apos;s your weight?</label>
              <div className={styles.suffixWrap}>
                <input
                  className={styles.suffixInput}
                  placeholder="0"
                  type="number"
                  min="0"
                  value={weight}
                  onChange={e => setWeight(e.target.value)}
                />
                <span className={styles.suffix}>lb</span>
              </div>
            </div>

            {error && <p className={styles.error}>{error}</p>}
            <button type="submit" className={styles.primaryBtn}>Continue</button>

            <p className={styles.divider}>
              Already have an account?
              <button type="button" className={styles.switchLink} onClick={() => switchMode('signin')}>Sign in</button>
            </p>
          </form>
        )}

        {mode === 'signup' && step === 2 && (
          <form onSubmit={handleSignUp}>
            <p className={styles.cardTitle}>Great, now for some logistics</p>

            <div className={styles.field}>
              <label className={styles.label}>Enter an email</label>
              <input className={styles.input} placeholder="email" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Create a password</label>
              <input className={styles.input} placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            </div>

            {error && <p className={styles.error}>{error}</p>}
            <button type="submit" className={styles.primaryBtn} disabled={loading}>
              {loading ? 'Creating account…' : 'Sign Up'}
            </button>
            <button type="button" className={styles.googleBtn} onClick={handleGoogle}>
              {GOOGLE_LOGO} Sign in with Google
            </button>

            <p className={styles.divider}>
              <button type="button" className={styles.switchLink} onClick={() => setStep(1)}>← Back</button>
            </p>
          </form>
        )}

        {mode === 'signin' && (
          <form onSubmit={handleSignIn}>
            <p className={styles.cardTitle}>Welcome back</p>

            <div className={styles.field}>
              <label className={styles.label}>Email</label>
              <input className={styles.input} placeholder="email" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Password</label>
              <input className={styles.input} placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            </div>

            {error && <p className={styles.error}>{error}</p>}
            <button type="submit" className={styles.primaryBtn} disabled={loading}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
            <button type="button" className={styles.googleBtn} onClick={handleGoogle}>
              {GOOGLE_LOGO} Sign in with Google
            </button>

            <p className={styles.divider}>
              No account?
              <button type="button" className={styles.switchLink} onClick={() => switchMode('signup')}>Sign up</button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
