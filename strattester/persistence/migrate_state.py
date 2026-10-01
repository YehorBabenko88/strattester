def copy_jobs(source,target):
    copied=0
    for job in source.list_jobs():
        target.put_job(job)
        check=target.get_job(job.id)
        if check!=job: raise RuntimeError(f'state verification failed for {job.id}')
        copied+=1
    return copied
