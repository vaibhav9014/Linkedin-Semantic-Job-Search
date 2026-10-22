import { useState, useCallback, useEffect } from 'react'
import UploadZone from './components/UploadZone'
import ScanningState from './components/ScanningState'
import ResumeSummary from './components/ResumeSummary'
import JobCard from './components/JobCard'
import ErrorBanner from './components/ErrorBanner'
import {
  beginLinkedInSignIn,
  checkHealth,
  getLinkedInProfile,
  matchResume,
} from './utils/api'
import styles from './App.module.css'

const STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  RESULTS: 'results',
  ERROR: 'error',
}

export default function App() {
  const [status, setStatus] = useState(STATUS.IDLE)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [backendUp, setBackendUp] = useState(null)
  const [profile, setProfile] = useState(null)
  const [locationFilter, setLocationFilter] = useState('')
  const [experienceFilter, setExperienceFilter] = useState('')
  const [postedFilter, setPostedFilter] = useState('')

  useEffect(() => {
    checkHealth().then((health) => {
      setBackendUp(!!health?.job_store_ready)
    })
    getLinkedInProfile().then(setProfile).catch(() => setProfile(null))
  }, [])

  const handleFileSelected = useCallback(async (file) => {
    setStatus(STATUS.LOADING)
    setError(null)
    try {
      const data = await matchResume(file, 10)
      setResult(data)
      setLocationFilter('')
      setExperienceFilter('')
      setPostedFilter('')
      setStatus(STATUS.RESULTS)
    } catch (err) {
      setError(err.message || 'Something went wrong.')
      setStatus(STATUS.ERROR)
    }
  }, [])

  const handleReset = useCallback(() => {
    setStatus(STATUS.IDLE)
    setResult(null)
    setError(null)
  }, [])

  const visibleJobs = result?.matches.filter((job) => {
    const matchesLocation = !locationFilter
      || job.location.toLowerCase().includes(locationFilter.toLowerCase())
    const level = (job.experience_level || '').toLowerCase()
    const matchesExperience = !experienceFilter || level.includes(experienceFilter)
    const postedAt = job.posted_at ? new Date(job.posted_at).getTime() : null
    const age = postedAt === null ? null : Date.now() - postedAt
    const matchesDate = !postedFilter || (
      age !== null && age <= Number(postedFilter) * 24 * 60 * 60 * 1000
    )
    return matchesLocation && matchesExperience && matchesDate
  }) || []

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.account}>
          {profile?.profile?.name && <span>Signed in as {profile.profile.name}</span>}
          {!profile?.profile && (
            <button className={styles.signIn} type="button" onClick={beginLinkedInSignIn}>
              Sign in with LinkedIn
            </button>
          )}
        </div>
        <p className={styles.eyebrow}>Semantic Job Match</p>
        <h1 className={styles.headline}>
          Find the roles your resume<br />actually fits.
        </h1>
        <p className={styles.subhead}>
          Upload a resume. Sentence-BERT searches live LinkedIn-published job listings
          for semantic matches, then highlights skills that match or may be missing.
        </p>
      </header>

      <main className={styles.main}>
        {backendUp === false && (
          <ErrorBanner
            message="Can't reach the matching server. Make sure the backend is running on port 8000."
            onDismiss={() => setBackendUp(null)}
          />
        )}

        {status === STATUS.ERROR && (
          <ErrorBanner message={error} onDismiss={handleReset} />
        )}

        {(status === STATUS.IDLE || status === STATUS.ERROR) && (
          <UploadZone onFileSelected={handleFileSelected} disabled={false} />
        )}

        {status === STATUS.LOADING && <ScanningState />}

        {status === STATUS.RESULTS && result && (
          <>
            <ResumeSummary
              skills={result.resume_skills}
              jobCount={result.total_jobs_searched}
              onReset={handleReset}
            />
            <p className={styles.searchQueries}>
              Search queries: {result.search_queries.join(' · ')}
            </p>
            <section className={styles.filters} aria-label="Filter job matches">
              <label>
                Location
                <input
                  type="search"
                  value={locationFilter}
                  onChange={(event) => setLocationFilter(event.target.value)}
                  placeholder="City, state, or country"
                />
              </label>
              <label>
                Experience
                <select value={experienceFilter} onChange={(event) => setExperienceFilter(event.target.value)}>
                  <option value="">Any experience</option>
                  <option value="intern">Internship</option>
                  <option value="entry">Entry level</option>
                  <option value="mid">Mid level</option>
                  <option value="senior">Senior level</option>
                </select>
              </label>
              <label>
                Date posted
                <select value={postedFilter} onChange={(event) => setPostedFilter(event.target.value)}>
                  <option value="">Any time</option>
                  <option value="1">Past 24 hours</option>
                  <option value="7">Past 7 days</option>
                  <option value="30">Past 30 days</option>
                </select>
              </label>
            </section>
            <div className={styles.results}>
              {visibleJobs.length === 0 ? (
                <p className={styles.empty}>
                  {result.matches.length === 0
                    ? 'No LinkedIn-published listings were returned for this resume. Try a different resume or location.'
                    : 'No jobs match the selected filters. Adjust the filters to see more.'}
                </p>
              ) : (
                visibleJobs.map((job, i) => (
                  <JobCard key={job.job_id} job={job} rank={i + 1} />
                ))
              )}
            </div>
          </>
        )}
      </main>

      <footer className={styles.footer}>
        <p>Built with Sentence-BERT, FAISS, and FastAPI.</p>
      </footer>
    </div>
  )
}
