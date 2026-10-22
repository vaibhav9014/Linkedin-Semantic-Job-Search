import styles from './ResumeSummary.module.css'

export default function ResumeSummary({ skills, jobCount, onReset }) {
  return (
    <div className={styles.wrapper}>
      <div>
        <p className={styles.eyebrow}>Detected skills</p>
        <div className={styles.skills}>
          {skills.length > 0 ? (
            skills.map((s) => <span key={s} className={styles.skill}>{s}</span>)
          ) : (
            <span className={styles.noneFound}>No keyword skills detected — matches are based on full-text similarity.</span>
          )}
        </div>
      </div>
      <div className={styles.right}>
        <p className={styles.count}>
          <span className={styles.countNum}>{jobCount}</span> jobs searched
        </p>
        <button className={styles.resetBtn} onClick={onReset}>Try another resume</button>
      </div>
    </div>
  )
}
