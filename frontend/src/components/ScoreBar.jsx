import styles from './ScoreBar.module.css'

/**
 * Signal-strength style score bar — reinforces the "semantic signal"
 * metaphor of the product rather than a generic progress bar.
 */
export default function ScoreBar({ score }) {
  const pct = Math.round(score * 100)
  const label = scoreLabel(score)

  return (
    <div className={styles.wrapper}>
      <div className={styles.track} role="img" aria-label={`Match score ${pct} percent, ${label}`}>
        <div
          className={styles.fill}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={styles.meta}>
        <span className={styles.score}>{pct}%</span>
        <span className={styles.label}>{label}</span>
      </div>
    </div>
  )
}

function scoreLabel(score) {
  if (score >= 0.80) return 'Excellent match'
  if (score >= 0.65) return 'Strong match'
  if (score >= 0.50) return 'Good match'
  if (score >= 0.35) return 'Partial match'
  return 'Weak match'
}
