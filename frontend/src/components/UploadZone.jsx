import { useState, useRef, useCallback } from 'react'
import styles from './UploadZone.module.css'

/**
 * Drag-and-drop PDF upload zone.
 * Calls onFileSelected(file) when a valid PDF is chosen.
 */
export default function UploadZone({ onFileSelected, disabled }) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const validateAndEmit = useCallback((file) => {
    if (!file) return
    if (file.type !== 'application/pdf') {
      setError('Only PDF files are accepted. Try exporting your resume as a PDF.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError(`File is ${(file.size / 1024 / 1024).toFixed(1)}MB — max size is 5MB.`)
      return
    }
    setError(null)
    onFileSelected(file)
  }, [onFileSelected])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    if (disabled) return
    const file = e.dataTransfer.files?.[0]
    validateAndEmit(file)
  }, [disabled, validateAndEmit])

  const handleChange = useCallback((e) => {
    const file = e.target.files?.[0]
    validateAndEmit(file)
  }, [validateAndEmit])

  return (
    <div className={styles.wrapper}>
      <div
        className={`${styles.zone} ${isDragging ? styles.dragging : ''} ${disabled ? styles.disabled : ''}`}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="Upload resume PDF"
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
      >
        <svg className={styles.icon} width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path d="M16 4v16m0 0l-6-6m6 6l6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M6 24v3a2 2 0 002 2h16a2 2 0 002-2v-3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <p className={styles.primaryText}>
          Drop your resume here, or <span className={styles.link}>browse</span>
        </p>
        <p className={styles.secondaryText}>PDF only, up to 5MB</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          onChange={handleChange}
          className={styles.hiddenInput}
          disabled={disabled}
        />
      </div>
      {error && (
        <p className={styles.errorText} role="alert">{error}</p>
      )}
    </div>
  )
}
