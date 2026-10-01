"""Clean only one generated operation's staging after a successful commit."""
import shutil


def finish_stage(stage, result):
    if result['status'] in {'ok', 'ok_with_warnings'}:
        try:
            shutil.rmtree(stage)
        except OSError as error:
            result = {**result, 'status': 'ok_with_warnings', 'diagnostics': [*result.get('diagnostics', []), {'code': 'STAGING_CLEANUP', 'severity': 'warning', 'message': str(error), 'hint': 'The write succeeded; inspect this operation staging directory before removing it.'}]}
    return result
