from ssyd import GPDownloader, ydl_opts, config, GPError, UnsupportedURLError, MetadataError, ProcessError, LimitExceededError

test_urls = ['yoursong1.link',
              'yoursong2.link' ]

destination = "C:/Music"

def run():
    try: 
        mainproc = GPDownloader(ydl_opts)
        mainproc.process('tracks', test_urls, destination, user_id=777)
    
    except LimitExceededError as e:
        print(f"[MOD] Access denied: {e}")
    except UnsupportedURLError as e:
        print(f"[CLIENT] The user provided a bad link: {e}")
    except MetadataError as e:
        print(f"[Data] Failed to collect tags: {e}")
    except ProcessError as e:
        print(f"[SYS] Download error/FFmpeg: {e}")
    except GPError as e:
        print(f"[SYS] Something went wrong.. {e}")
    except Exception as e:
        print(f"[CRITICAL] Code is broken, error details: {e}")

if __name__ == "__main__":
    run()