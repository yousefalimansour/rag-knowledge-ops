'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { ApiError } from '@/lib/api';
import { authApi } from '@/lib/auth';
import styles from '../auth.module.css';

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setPending(true);
    try {
      await authApi.signup(email, password);
      router.replace('/dashboard');
      router.refresh();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail || err.message : 'Signup failed';
      setError(detail);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.loginBox}>
        <form className={styles.form} onSubmit={onSubmit} noValidate>
          <div className={styles.logo} aria-hidden="true" />
          <span className={styles.header}>Create Account</span>

          {error && (
            <div className={styles.error} role="alert">
              {error}
            </div>
          )}

          <input
            type="email"
            placeholder="Email"
            className={styles.input}
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password (8+ characters)"
            className={styles.input}
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button
            type="submit"
            className={`${styles.button} ${styles.signIn}`}
            disabled={pending}
          >
            {pending ? 'Creating…' : 'Sign Up'}
          </button>

          <p className={styles.footer}>
            Already have an account?{' '}
            <Link href="/login" className={styles.link}>
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
