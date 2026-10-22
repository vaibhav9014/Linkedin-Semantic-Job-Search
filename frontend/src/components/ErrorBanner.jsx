import styles from './ErrorBanner.module.css'

export default function ErrorBanner({ message, onDismiss }) {
  return (
    <div className={styles.banner} role="alert">
      <span className={styles.icon} aria-hidden="true">⚠</span>
      <p className={styles.message}>{message}</p>
      <button className={styles.dismiss} onClick={onDismiss} aria-label="Dismiss error">✕</button>
    </div>
  )
}
