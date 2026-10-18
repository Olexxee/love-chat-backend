# LoveChat notifications

## What is included

- Persistent in-app notifications for incoming messages, connection requests, and accepted connection requests.
- Expo push delivery to registered iOS, Android, or web device tokens.
- Per-user controls for push notifications, message push alerts, and connection push alerts.
- Authenticated endpoints for listing, reading, and registering devices.
- Invalid Expo tokens are deactivated when Expo returns `DeviceNotRegistered`.

Push delivery is best-effort and does not replace the existing WebSocket messaging or durable delivery-event flow. The notification inbox is stored in the database.

## Database migration

This feature adds Alembic revision `20261018_0004`, following `20261018_0003` (password reset tokens).

Before running migrations against production, verify the database's current Alembic revision and compare its actual schema to the migration history. Do not recreate or reset the production database to apply this feature.

After verification, deploy the backend and run the project's normal migration command:

```bash
alembic upgrade head
```

## Expo push credentials

The backend sends push messages through Expo Push Service and does not require an Expo access token for the basic push endpoint.

Device tokens can be registered before platform delivery credentials are configured, but successful delivery requires the appropriate native credentials:
- Android: configure Firebase Cloud Messaging (FCM v1) credentials for the EAS project.
- iOS: configure APNs credentials for the EAS project.

Use the EAS credentials workflow and keep private service-account/APNs keys out of GitHub and the app bundle. Remote push notifications require a fresh native build after adding `expo-notifications`; Expo Go is not a valid Android remote-push test target for this SDK.

## API

All endpoints require the existing authenticated access cookie.

- `GET /api/notifications?limit=50&before_id=123` — latest notifications and unread count.
- `PATCH /api/notifications/{notification_id}/read` — mark one notification as read.
- `POST /api/notifications/read-all` — mark all notifications as read.
- `POST /api/notifications/devices` — register an Expo push token.
- `DELETE /api/notifications/devices/{device_id}` — deactivate a device token.
- `GET /api/notifications/preferences` — read push preferences.
- `PATCH /api/notifications/preferences` — update one or more preference booleans.

Example device registration body:

```json
{
  "expo_push_token": "ExponentPushToken[...token...]",
  "platform": "android",
  "device_name": "Android phone"
}
```
