from core.logger import logger

def fetch_form_structure(service, form_id: str) -> dict:
    form = service.forms().get(formId=form_id).execute()
    logger.info("Fetched form structure for %s", form_id)
    return form

def fetch_all_responses(service, form_id: str) -> list[dict]:
    all_responses, page_token = [], None
    while True:
        req = service.forms().responses().list(formId=form_id, pageToken=page_token)
        resp = req.execute()
        all_responses.extend(resp.get("responses", []) or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    logger.info("Fetched %d responses for form %s", len(all_responses), form_id)
    return all_responses
