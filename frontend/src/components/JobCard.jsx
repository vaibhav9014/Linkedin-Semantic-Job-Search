import { useState } from 'react'
import ScoreBar from './ScoreBar'
import SkillTags from './SkillTags'
import { ApiError, beginLinkedInSharePermission, beginLinkedInSignIn, shareJobMatch } from '../utils/api'
import styles from './JobCard.module.css'

export default function JobCard({ job, rank }) {
  const [shareOpen, setShareOpen] = useState(false)
  const [commentary, setCommentary] = useState(
    `I found this ${job.title} role at ${job.company} on ${job.source}.${job.apply_url ? ` Apply here: ${job.apply_url}` : ''}`
  )
  const [shareError, setShareError] = useState('')
  const [sharing, setSharing] = useState(false)
  const [published, setPublished] = useState(false)

  const handleConfirmShare = async () => {
    setSharing(true)
    setShareError('')
    try {
      await shareJobMatch(job, commentary)
      setPublished(true)
      setShareOpen(false)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setShareError('Sign in with LinkedIn, then confirm the post again.')
      } else if (error instanceof ApiError && error.code === 'sharing_permission_required') {
        setShareError('LinkedIn requires your separate permission before the first post.')
      } else {
        setShareError(error.message || 'Could not publish the post.')
      }
    } finally {
      setSharing(false)
    }
  }

  return (
    <article className={styles.card}>
      <div className={styles.rank}>{String(rank).padStart(2, '0')}</div>
      <div className={styles.body}>
        <div className={styles.header}>
          <div>
            <h3 className={styles.title}>{job.title}</h3>
            <p className={styles.company}>
              {job.company}
              {job.location && <span className={styles.location}> · {job.location}</span>}
            </p>
          </div>
          <ScoreBar score={job.score} />
        </div>
        <p className={styles.snippet}>{job.description_snippet}</p>
        <SkillTags matched={job.matched_skills} missing={job.missing_skills} />
        <div className={styles.jobMeta}>
          <span className={styles.source}>{job.source}</span>
          {job.salary && <span>{job.salary}</span>}
          {job.experience_level && <span>{job.experience_level}</span>}
          {job.posted_at && <span>Posted {new Date(job.posted_at).toLocaleDateString()}</span>}
        </div>
        <div className={styles.actions}>
          {job.apply_url && (
            <a className={styles.applyLink} href={job.apply_url} target="_blank" rel="noreferrer">
              View job and apply
            </a>
          )}
          {published ? (
            <span className={styles.published}>Posted to LinkedIn</span>
          ) : (
            <button
              className={styles.shareButton}
              type="button"
              onClick={() => { setShareOpen((open) => !open); setShareError('') }}
            >
              Share on LinkedIn
            </button>
          )}
        </div>
        {shareOpen && (
          <div className={styles.sharePreview}>
            <label htmlFor={`share-comment-${job.job_id}`}>Post preview</label>
            <textarea
              id={`share-comment-${job.job_id}`}
              value={commentary}
              maxLength={3000}
              onChange={(event) => setCommentary(event.target.value)}
              rows={4}
            />
            <div className={styles.actions}>
              <button
                className={styles.shareButton}
                type="button"
                disabled={sharing || !commentary.trim()}
                onClick={handleConfirmShare}
              >
                {sharing ? 'Publishing…' : 'Confirm and post'}
              </button>
              <button className={styles.cancelButton} type="button" onClick={() => setShareOpen(false)}>
                Cancel
              </button>
            </div>
            {shareError && (
              <div className={styles.shareError} role="alert">
                <p>{shareError}</p>
                {shareError.includes('Sign in') && (
                  <button className={styles.textButton} type="button" onClick={beginLinkedInSignIn}>
                    Sign in with LinkedIn
                  </button>
                )}
                {shareError.includes('permission') && (
                  <button className={styles.textButton} type="button" onClick={beginLinkedInSharePermission}>
                    Authorize LinkedIn sharing
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
