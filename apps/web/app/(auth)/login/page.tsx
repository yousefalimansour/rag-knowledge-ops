import { Suspense } from 'react';
import styles from '../auth.module.css';
import { LoginForm } from './login-form';

export default function LoginPage() {
  return (
    <Suspense fallback={<div className={styles.suspenseFallback}>Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
