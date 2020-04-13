import time

from webhook_handlers import run_conversation_check_scan_for_prs


def main():
    while True:
        run_conversation_check_scan_for_prs('li-foundation', 'zac-test-repo')
        time.sleep(10)


if __name__ == '__main__':
    main()
