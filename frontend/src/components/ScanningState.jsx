import styles from './ScanningState.module.css'

/**
 * Signature loading visual: a horizontal scan-line sweeping over
 * a field of faint dots, evoking embedding/vector search rather
 * than a generic spinner. This is the page's one deliberate flourish.
 */
export default function ScanningState() {
  return (
    <div className={styles.wrapper} role="status" aria-live="polite">
      <div className={styles.field}>
        {Array.from({ length: 48 }).map((_, i) => (
          <span key={i} className={styles.dot} style={{ animationDelay: `${(i % 8) * 0.08}s` }} />
        ))}
        <div className={styles.scanline} />
      </div>
      <p className={styles.text}>Embedding resume and searching the index…</p>
    </div>
  )
}
