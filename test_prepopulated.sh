#!/bin/bash
TOKEN="9cea828f83fcbec6bf9141b6e149a2f2caee0d75da5329d9202b503c7863a0b8"
BASE_URL="http://localhost:6969"

echo "============================================================"
echo "TESTING: Modal Opens with Prepopulated URI and APIKey"
echo "============================================================"
echo ""
echo "This test simulates what happens when you:"
echo "1. Click 'Configure' on Radarr-1080"
echo "2. Modal opens with URI and APIKey already populated from config"
echo "3. You click the 'Test' button"
echo ""

# Step 1: Get the config (simulates what the UI does when loading the modal)
echo "Step 1: Loading Radarr-1080 config (simulates modal opening)"
echo "-----------------------------------------------------------"
CONFIG=$(curl -s "$BASE_URL/api/config" -H "Authorization: Bearer $TOKEN")
RADARR_URI=$(echo "$CONFIG" | python3 -c "import sys, json; print(json.load(sys.stdin)['Radarr-1080']['URI'])")
RADARR_KEY=$(echo "$CONFIG" | python3 -c "import sys, json; print(json.load(sys.stdin)['Radarr-1080']['APIKey'])")

echo "✓ Modal would open with these values prepopulated:"
echo "  URI field: $RADARR_URI"
echo "  APIKey field: ${RADARR_KEY:0:10}..."
echo ""

# Step 2: Simulate clicking the Test button with those prepopulated values
echo "Step 2: User clicks 'Test' button (with prepopulated values)"
echo "------------------------------------------------------------"
echo "Calling: POST /api/arr/test-connection"
echo "  With URI: $RADARR_URI"
echo "  With APIKey: ${RADARR_KEY:0:10}..."
echo ""

RESULT=$(curl -s -X POST "$BASE_URL/api/arr/test-connection" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"arrType\":\"radarr\",\"uri\":\"$RADARR_URI\",\"apiKey\":\"$RADARR_KEY\"}")

SUCCESS=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")
MESSAGE=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))")

echo "Response received:"
echo "-----------------------------------------------------------"
if [ "$SUCCESS" = "True" ]; then
    echo "✅ SUCCESS!"
    echo ""
    echo "Message: $MESSAGE"
    echo ""

    VERSION=$(echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('systemInfo', {}).get('version', 'N/A'))")
    BRANCH=$(echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('systemInfo', {}).get('branch', 'N/A'))")
    PROFILES=$(echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); profiles=d.get('qualityProfiles', []); print('\\n'.join([f\"  - {p['name']}\" for p in profiles]))")
    PROFILE_COUNT=$(echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('qualityProfiles', [])))")

    echo "System Info:"
    echo "  Version: $VERSION"
    echo "  Branch: $BRANCH"
    echo ""
    echo "Quality Profiles ($PROFILE_COUNT found):"
    echo "$PROFILES"
    echo ""
    echo "============================================================"
    echo "✅ FIX VERIFIED: Test works with prepopulated credentials!"
    echo "============================================================"
    echo ""
    echo "The modal would now show:"
    echo "  • Success alert with version info"
    echo "  • Quality profile dropdowns populated with $PROFILE_COUNT profiles"
    echo "  • No 'populate uri and api fields' error"
else
    echo "❌ FAILED!"
    echo ""
    echo "Message: $MESSAGE"
    echo ""
    echo "============================================================"
    echo "❌ FIX NOT WORKING: Still showing error with prepopulated data"
    echo "============================================================"
    exit 1
fi
