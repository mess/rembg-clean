(define (print-args proc-name)
  (let* (
         (info (gimp-procedural-db-proc-info proc-name))
         (args (caddr (cddr (cddr (cddr info))))) ;; Skip to args list
        )
    (gimp-message (string-append "Info for " proc-name ": " (symbol->string (car args))))
  )
)

;; gimp-procedural-db-proc-info returns:
;; (blurb help author copyright date type n-params n-return-vals params return-vals)
;; We want to inspect 'params'.

(let* ((info (gimp-procedural-db-proc-info "gimp-file-save")))
  (gimp-message "gimp-file-save params:")
  (gimp-message (number->string (nth 6 info))) ;; n-params
  (let ((params (nth 8 info)))
    (while (not (null? params))
      (let ((param (car params)))
        ;; param is (type name description)
        (gimp-message (string-append "Type: " (number->string (car param)) " Name: " (cadr param)))
      )
      (set! params (cdr params))
    )
  )
)

(gimp-quit 0)
