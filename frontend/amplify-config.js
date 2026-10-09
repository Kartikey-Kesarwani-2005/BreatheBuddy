// Optional runtime config for the AWS deployment (Amplify Hosting + Cognito).
// On AWS, replace the values below with your API Gateway URL and Cognito pool.
// Locally this file leaves apiBase empty so the app talks to the same origin.
window.BB_CONFIG = {
  apiBase: "",               // e.g. "https://abc123.execute-api.ap-south-1.amazonaws.com/prod"
  cognito: null              // e.g. { hostedUi: "https://<domain>.auth.<region>.amazoncognito.com/login?client_id=...&response_type=token&scope=email+openid&redirect_uri=..." }
};
