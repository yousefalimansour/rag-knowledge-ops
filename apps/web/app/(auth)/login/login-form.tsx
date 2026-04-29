'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { ApiError } from '@/lib/api';
import { authApi } from '@/lib/auth';
import styles from '../auth.module.css';

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/dashboard';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await authApi.login(email, password);
      router.replace(next);
      router.refresh();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail || err.message : 'Login failed';
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
          <span className={styles.header}>Welcome Back!</span>

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
            placeholder="Password"
            className={styles.input}
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button
            type="submit"
            className={`${styles.button} ${styles.signIn}`}
            disabled={pending}
          >
            {pending ? 'Signing in…' : 'Sign In'}
          </button>

          <p className={styles.footer}>
            Don&apos;t have an account?{' '}
            <Link href="/signup" className={styles.link}>
              Sign up, it&apos;s free!
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
