# Debug Test Connection Issues

## Step 1: Verify the WebUI is serving the latest build

Open your browser and check:

```
http://YOUR_QBITRR_IP:6969/ui
```

## Step 2: Check if the fix is deployed

Open browser DevTools (F12) → Network tab → Refresh the page

Look for the ConfigView.js file and check:
- Size should be approximately 64 KB
- Check the timestamp/version

## Step 3: Open the Arr Instance Modal

1. Go to Config tab
2. Click "Configure" on any Radarr/Sonarr/Lidarr instance
3. Modal should open with prepopulated fields

**Check:**
- Does URI field show your Arr instance URL?
- Does APIKey field show your API key?
- Does Test button say just "Test" (not "Test Connection")?
- Is there NO checkmark icon on the Test button?

## Step 4: Check Browser Console for Errors

Open DevTools (F12) → Console tab

Click the Test button and look for:
- Any red errors
- Network requests to `/api/arr/test-connection`
- Response from the API

## Step 5: Check Network Request

DevTools → Network tab → Click Test button

Look for the POST request to `/api/arr/test-connection`:

**Request payload should show:**
```json
{
  "arrType": "radarr",
  "uri": "http://YOUR_ARR_IP:PORT",
  "apiKey": "YOUR_ACTUAL_API_KEY"
}
```

**If uri or apiKey are empty/undefined, the fix isn't deployed yet.**

## Step 6: Check API Response

Still in Network tab, click on the test-connection request:

**Response tab should show:**
```json
{
  "success": true,
  "message": "Connected successfully",
  "systemInfo": {...},
  "qualityProfiles": [...]
}
```

**OR if failed:**
```json
{
  "success": false,
  "message": "ERROR_MESSAGE_HERE"
}
```

## Common Issues:

### Issue: "Missing required fields: arrType, uri, or apiKey"
**Cause:** Request payload has empty uri or apiKey
**Fix:** The getValue fix isn't deployed - rebuild and redeploy

### Issue: "Unauthorized: Invalid API key"
**Cause:** Wrong API key being sent
**Fix:** Check config.toml has correct APIKey

### Issue: Connection timeout
**Cause:** Network connectivity between qBitrr and Arr instance
**Fix:** Check network, firewall, DNS

### Issue: "Please configure URI and API Key first"
**Cause:** getValue is returning undefined
**Fix:** The fix isn't deployed - need to rebuild with latest commits

## Quick Test Command

If you have curl access to your qBitrr instance:

```bash
# Replace with your values
QBITRR_URL="http://YOUR_IP:6969"
TOKEN="YOUR_WEBUI_TOKEN"
ARR_URI="http://YOUR_RADARR_IP:7878"
ARR_KEY="YOUR_RADARR_API_KEY"

curl -X POST "$QBITRR_URL/api/arr/test-connection" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"arrType\":\"radarr\",\"uri\":\"$ARR_URI\",\"apiKey\":\"$ARR_KEY\"}"
```

Should return success if credentials are correct.
