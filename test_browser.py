"""Quick test: browser_use tools - navigate to vnstock.io and extract content."""

import sys
sys.path.insert(0, "agent")

def test_import():
    """Test that all browser_use modules import correctly."""
    print("1. Testing imports...")
    from tools.browser_use import BrowserToolSet
    from tools.browser_use.definition import (
        BrowserNavigateAction,
        BrowserGetContentAction,
        BrowserGetStateAction,
        BrowserObservation,
    )
    from tools.browser_use.impl import BrowserToolExecutor
    print("   All imports OK!")
    return BrowserToolExecutor, BrowserNavigateAction, BrowserGetContentAction, BrowserGetStateAction

def test_browser(url="https://vnstock.com"):
    """Test navigate + get_content on a real URL."""
    BrowserToolExecutor, BrowserNavigateAction, BrowserGetContentAction, BrowserGetStateAction = test_import()

    print(f"\n2. Initializing BrowserToolExecutor...")
    try:
        executor = BrowserToolExecutor(
            headless=True,
            init_timeout_seconds=60,
            chromium_sandbox=False,
        )
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    print(f"   Executor created OK!")

    print(f"\n3. Navigating to {url}...")
    action = BrowserNavigateAction(url=url)
    result = executor(action)
    print(f"   Navigate result: {result.text[:200] if result.text else '(empty)'}...")

    print(f"\n4. Getting page content...")
    action = BrowserGetContentAction(extract_links=False, start_from_char=0)
    result = executor(action)
    content = result.text or "(empty)"
    print(f"   Content length: {len(content)} chars")
    print(f"   First 500 chars:\n{'='*60}")
    print(content[:500])
    print(f"{'='*60}")

    print(f"\n5. Cleaning up...")
    executor.close()
    print("   Done!")

if __name__ == "__main__":
    if "--import-only" in sys.argv:
        test_import()
    else:
        test_browser()
