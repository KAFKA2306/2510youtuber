import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config_prompts.settings import settings
from app.prompts import get_sheet_prompt_defaults
logger = logging.getLogger(__name__)
class SheetsManager:
    def __init__(self):
        self.service = None
        self.sheet_id = settings.google_sheet_id
        self._connect()
    def _connect(self):
        try:
            creds_dict = settings.google_credentials_json
            if not creds_dict:
                logger.warning('Google credentials not configured - Sheets integration disabled')
                self.service = None
                return
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets'])
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info('Google Sheets connection established')
            self.setup_sheets()
        except Exception as e:
            logger.error(f'Failed to connect to Google Sheets: {e}')
            self.service = None
    def _rate_limit_retry(self, func, *args, **kwargs):
        import random
        import time
        if not self.service:
            raise RuntimeError('Sheets service not available')
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                time.sleep(0.1 + random.uniform(0, 0.1))
                return result
            except HttpError as e:
                if e.resp.status == 429 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(f'Rate limit hit, waiting {wait_time:.2f}s...')
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f'Sheets API error, retrying in {wait_time}s: {e}')
                    time.sleep(wait_time)
                    continue
                raise
        return None
    def create_run(self, mode: str='daily') -> str:
        if not self.service:
            logger.warning('Sheets service not available, returning dummy run_id')
            return str(uuid.uuid4())[:8]
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        values = [[run_id, 'processing', now, '', '', mode, '', '', '', '', '', '', '', '', '', '', '', '', '']]
        try:
            self._rate_limit_retry(self.service.spreadsheets().values().append, spreadsheetId=self.sheet_id, range='runs!A:S', valueInputOption='RAW', body={'values': values}).execute()
            logger.info(f'Created new run: {run_id} (mode: {mode})')
            return run_id
        except Exception as e:
            logger.error(f'Failed to create run: {e}')
            raise
    def update_run(self, run_id: str, **fields) -> bool:
        if not self.service:
            logger.debug(f'Sheets service unavailable, skipping update for run {run_id}')
            return False
        try:
            result = self._rate_limit_retry(self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range='runs!A:S').execute()
            rows = result.get('values', [])
            target_row_index = None
            for i, row in enumerate(rows):
                if len(row) > 0 and row[0] == run_id:
                    target_row_index = i
                    break
            if target_row_index is None:
                logger.error(f'Run ID not found: {run_id}')
                return False
            current_row = rows[target_row_index]
            while len(current_row) < 19:
                current_row.append('')
            field_mapping = {'status': 1, 'finished_at': 3, 'duration_sec': 4, 'mode': 5, 'prompt_a': 6, 'search_results_json': 7, 'script_text': 8, 'audio_urls_json': 9, 'stt_text': 10, 'subtitle_srt': 11, 'video_url': 12, 'title': 13, 'description': 14, 'sources': 15, 'thumbnail_url': 16, 'first_comment': 17, 'error_log': 18}
            for field, value in fields.items():
                if field in field_mapping:
                    col_index = field_mapping[field]
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        value = ''
                    str_value = str(value)
                    max_chars = 48000
                    if len(str_value) > max_chars:
                        truncate_msg = f'\n\n[TRUNCATED: Original length was {len(str_value)} characters]'
                        str_value = str_value[:max_chars - len(truncate_msg)] + truncate_msg
                        logger.warning(f"Field '{field}' truncated from {len(str(value))} to {len(str_value)} characters")
                    current_row[col_index] = str_value
            if fields.get('status') == 'completed' and 'finished_at' not in fields:
                current_row[3] = datetime.now().isoformat()
            if not self.service:
                logger.debug(f'Sheets service unavailable, skipping update for run {run_id}')
                return False
            range_name = f'runs!A{target_row_index + 1}:S{target_row_index + 1}'
            self._rate_limit_retry(self.service.spreadsheets().values().update, spreadsheetId=self.sheet_id, range=range_name, valueInputOption='RAW', body={'values': [current_row]}).execute()
            logger.info(f'Updated run {run_id}: {list(fields.keys())}')
            return True
        except Exception as e:
            logger.error(f'Failed to update run {run_id}: {e}')
            return False
    def load_prompts(self, mode: str='daily') -> Dict[str, str]:
        prompt_manager = settings.prompt_manager
        if not self.service:
            logger.warning('Sheets service not available, trying cache...')
            if hasattr(prompt_manager, 'load_prompts_from_cache'):
                cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                if cached_prompts:
                    logger.info(f"Using cached prompts for mode '{mode}'")
                    return cached_prompts
            logger.warning('No cache available, returning default prompts')
            return self._get_default_prompts()
        try:
            result = self._rate_limit_retry(self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range='prompts!A1:E10').execute()
            rows = result.get('values', [])
            logger.info(f"Loaded {len(rows)} rows from prompts sheet: {rows}")
            if len(rows) >= 2:
                headers = rows[0]
                mode_row_index = self._find_mode_row(rows, mode)
                values = rows[mode_row_index] if mode_row_index else rows[1]
                prompts = {}
                for i, header in enumerate(headers):
                    if i < len(values) and values[i]:
                        prompts[header] = values[i]
                default_prompts = self._get_default_prompts()
                for key in ['prompt_a', 'prompt_b', 'prompt_c', 'prompt_d']:
                    if key not in prompts or not prompts[key]:
                        prompts[key] = default_prompts.get(key, '')
                logger.info(f"Loaded {len(prompts)} prompts from Sheets for mode '{mode}'")
                if hasattr(prompt_manager, 'save_prompts_to_cache'):
                    prompt_manager.save_prompts_to_cache(mode, prompts)
                return prompts
            else:
                logger.warning('Prompts sheet is empty or malformed, trying cache...')
                if hasattr(prompt_manager, 'load_prompts_from_cache'):
                    cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                    if cached_prompts:
                        return cached_prompts
                return self._get_default_prompts()
        except Exception as e:
            logger.error(f'Failed to load prompts from Sheets: {e}, trying cache...')
            if hasattr(prompt_manager, 'load_prompts_from_cache'):
                cached_prompts = prompt_manager.load_prompts_from_cache(mode)
                if cached_prompts:
                    logger.info(f"Using cached prompts as fallback for mode '{mode}'")
                    return cached_prompts
            logger.warning('No cache available, returning default prompts')
            return self._get_default_prompts()
    def _find_mode_row(self, rows: List[List[str]], mode: str) -> Optional[int]:
        mode_column_index = 0
        for i, row in enumerate(rows[1:], start=1):
            if len(row) > mode_column_index and row[mode_column_index].lower() == mode.lower():
                logger.info(f"Found mode-specific prompts for '{mode}' at row {i + 1}")
                return i
        return None
    def update_prompt(self, prompt_name: str, prompt_content: str, mode: str='daily') -> bool:
        if not self.service:
            logger.warning('Sheets service not available')
            return False
        try:
            result = self._rate_limit_retry(self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range='prompts!A1:E10').execute()
            rows = result.get('values', [])
            if not rows:
                logger.error('Prompts sheet is empty')
                return False
            headers = rows[0]
            prompt_col_index = None
            for i, header in enumerate(headers):
                if header == prompt_name:
                    prompt_col_index = i
                    break
            if prompt_col_index is None:
                logger.error(f"Prompt '{prompt_name}' not found in headers")
                return False
            mode_row_index = self._find_mode_row(rows, mode)
            if mode_row_index is None:
                logger.warning(f"Mode '{mode}' not found, updating default row")
                mode_row_index = 1
            while len(rows[mode_row_index]) <= prompt_col_index:
                rows[mode_row_index].append('')
            rows[mode_row_index][prompt_col_index] = prompt_content
            col_letter = chr(65 + prompt_col_index)
            range_name = f'prompts!{col_letter}{mode_row_index + 1}'
            self._rate_limit_retry(self.service.spreadsheets().values().update, spreadsheetId=self.sheet_id, range=range_name, valueInputOption='RAW', body={'values': [[prompt_content]]}).execute()
            logger.info(f"Updated {prompt_name} for mode '{mode}'")
            return True
        except Exception as e:
            logger.error(f'Failed to update prompt: {e}')
            return False
    def record_prompt_used(self, run_id: str, prompt_name: str, prompt_content: str) -> bool:
        field_name = prompt_name
        return self.update_run(run_id, **{field_name: prompt_content})
    def get_prompt_analytics(self) -> Dict[str, Any]:
        if not self.service:
            logger.warning('Sheets service not available')
            return {}
        try:
            result = self._rate_limit_retry(self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range='runs!A:S').execute()
            rows = result.get('values', [])
            if len(rows) <= 1:
                return {'total_runs': 0, 'prompts': {}}
            headers = rows[0]
            data_rows = rows[1:]
            analytics = {'total_runs': len(data_rows), 'successful_runs': sum((1 for row in data_rows if len(row) > 1 and row[1] == 'completed')), 'failed_runs': sum((1 for row in data_rows if len(row) > 1 and row[1] == 'failed')), 'prompts': {}, 'mode_distribution': {}}
            mode_col_index = headers.index('mode') if 'mode' in headers else 5
            for row in data_rows:
                if len(row) > mode_col_index:
                    mode = row[mode_col_index]
                    analytics['mode_distribution'][mode] = analytics['mode_distribution'].get(mode, 0) + 1
            logger.info(f"Analyzed {analytics['total_runs']} runs")
            return analytics
        except Exception as e:
            logger.error(f'Failed to get prompt analytics: {e}')
            return {}
    def create_prompt_version(self, prompt_name: str, version_note: str='') -> bool:
        if not self.service:
            logger.warning('Sheets service not available')
            return False
        try:
            spreadsheet = self._rate_limit_retry(self.service.spreadsheets().get, spreadsheetId=self.sheet_id).execute()
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
            if 'prompt_history' not in existing_sheets:
                self._create_sheet('prompt_history', ['timestamp', 'prompt_name', 'mode', 'prompt_content', 'version_note', 'created_by'])
            current_prompts = self.load_prompts('daily')
            if prompt_name not in current_prompts:
                logger.error(f"Prompt '{prompt_name}' not found")
                return False
            from datetime import datetime
            now = datetime.now().isoformat()
            history_row = [now, prompt_name, 'daily', current_prompts[prompt_name], version_note, 'system']
            self._rate_limit_retry(self.service.spreadsheets().values().append, spreadsheetId=self.sheet_id, range='prompt_history!A:F', valueInputOption='RAW', body={'values': [history_row]}).execute()
            logger.info(f'Saved version of {prompt_name} to history')
            return True
        except Exception as e:
            logger.error(f'Failed to create prompt version: {e}')
            return False
    def _get_default_prompts(self) -> Dict[str, str]:
        return get_sheet_prompt_defaults()
    def get_recent_runs(self, limit: int=10) -> List[Dict[str, Any]]:
        try:
            result = self._rate_limit_retry(self.service.spreadsheets().values().get, spreadsheetId=self.sheet_id, range='runs!A:S').execute()
            rows = result.get('values', [])
            if len(rows) <= 1:
                return []
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            recent_runs = []
            for row in reversed(data_rows[-limit:]):
                run_data = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        run_data[header] = row[i]
                    else:
                        run_data[header] = ''
                recent_runs.append(run_data)
            return recent_runs
        except Exception as e:
            logger.error(f'Failed to get recent runs: {e}')
            return []
    def setup_sheets(self) -> bool:
        try:
            spreadsheet = self._rate_limit_retry(self.service.spreadsheets().get, spreadsheetId=self.sheet_id).execute()
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
            required_sheets = {'runs': ['run_id', 'status', 'started_at', 'finished_at', 'duration_sec', 'mode', 'prompt_a', 'search_results_json', 'script_text', 'audio_urls_json', 'stt_text', 'subtitle_srt', 'video_url', 'title', 'description', 'sources', 'thumbnail_url', 'first_comment', 'error_log'], 'prompts': ['mode', 'prompt_a', 'prompt_b', 'prompt_c', 'prompt_d']}
            for sheet_name, headers in required_sheets.items():
                if sheet_name not in existing_sheets:
                    logger.info(f'Creating sheet: {sheet_name}')
                    self._create_sheet(sheet_name, headers)
            return True
        except Exception as e:
            logger.error(f'Failed to setup sheets: {e}')
            return False
    def _create_sheet(self, sheet_name: str, headers: List[str]):
        request_body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
        self._rate_limit_retry(self.service.spreadsheets().batchUpdate, spreadsheetId=self.sheet_id, body=request_body).execute()
        self._rate_limit_retry(self.service.spreadsheets().values().update, spreadsheetId=self.sheet_id, range=f'{sheet_name}!A1', valueInputOption='RAW', body={'values': [headers]}).execute()
        if sheet_name == 'prompts':
            self._initialize_default_prompt_modes()
        logger.info(f"Created sheet '{sheet_name}' with headers")
    def _initialize_default_prompt_modes(self):
        try:
            default_prompts = self._get_default_prompts()
            modes_data = [['daily', default_prompts['prompt_a'], default_prompts['prompt_b'], default_prompts['prompt_c'], default_prompts['prompt_d']], ['special', '', '', '', ''], ['test', '', '', '', '']]
            self._rate_limit_retry(self.service.spreadsheets().values().update, spreadsheetId=self.sheet_id, range='prompts!A2:E4', valueInputOption='RAW', body={'values': modes_data}).execute()
            logger.info('Initialized default prompt modes (daily, special, test)')
        except Exception as e:
            logger.error(f'Failed to initialize default prompt modes: {e}')
sheets_manager = SheetsManager() if settings.google_sheet_id else None
def get_sheets() -> Optional[SheetsManager]:
    return sheets_manager
def create_run(mode: str='daily') -> str:
    if sheets_manager:
        return sheets_manager.create_run(mode)
    else:
        import time
        return f'fallback_{int(time.time())}'
def update_run(run_id: str, **fields) -> bool:
    if sheets_manager:
        return sheets_manager.update_run(run_id, **fields)
    else:
        logger.warning(f'Sheets not available, skipping update for {run_id}')
        return False
def load_prompts(mode: str='daily') -> Dict[str, str]:
    if sheets_manager:
        return sheets_manager.load_prompts(mode)
    else:
        logger.warning('Sheets not available, using default prompts')
        return SheetsManager()._get_default_prompts()