import styles from './SkillTags.module.css'

/**
 * Renders matched skills (green) and missing skills (amber outline).
 * This is the "explainability" layer — why a job matched, and the gap to close.
 */
export default function SkillTags({ matched, missing }) {
  if (matched.length === 0 && missing.length === 0) return null

  return (
    <div className={styles.wrapper}>
      {matched.length > 0 && (
        <div className={styles.row}>
          {matched.map((skill) => (
            <span key={skill} className={styles.matched}>{skill}</span>
          ))}
        </div>
      )}
      {missing.length > 0 && (
        <div className={styles.row}>
          {missing.slice(0, 6).map((skill) => (
            <span key={skill} className={styles.missing}>+ {skill}</span>
          ))}
        </div>
      )}
    </div>
  )
}
