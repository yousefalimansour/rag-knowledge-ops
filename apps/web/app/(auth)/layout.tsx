import styles from './auth.module.css';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main className={styles.page}>{children}</main>;
}
