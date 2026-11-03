# In a function so bash reads all of it before running any: updates
# replace this file while it runs
main() {
    clear && python3 update.py || exit 1
    while true; do
        if [ -f .pr_test ]; then
            # Kept to report why, if the PR being tested crashes
            python3 -m bot 2> >(tee .bot_stderr.log >&2)
        else
            python3 -m bot
        fi
        code=$?
        # Clean exits and stops (Ctrl+C, SIGTERM, SIGKILL) end here as before
        case $code in 0|130|137|143) exit $code ;; esac
        # A crash while testing a PR goes back to main and starts again;
        # any other crash ends here as before
        [ -f .pr_test ] || exit $code
        python3 update.py --revert $code
        if [ -f .pr_test ]; then
            # The PR's update.py predates --revert: update the old way
            rm -f .pr_test && touch update && python3 update.py
        fi
    done
}
main
exit
