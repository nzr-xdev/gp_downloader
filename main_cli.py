from ssyd import GPDownloader, GPError, UnsupportedURLError, MetadataError, ProcessError, LimitExceededError

test_urls = ['https://soundcloud.com/bucur-darius-162711084/nevermind-kvpv-bass-boosted?in=hczh-hzhh/sets/bibika/s-ptMqv99ke9J&si=7bb444a73e784e129c73190cc08a70cd&utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing']

destination = "W:/g-player_project/test"

def run():
    try: 
        mainproc = GPDownloader()
        mainproc.process('tracks', test_urls, destination)
    
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