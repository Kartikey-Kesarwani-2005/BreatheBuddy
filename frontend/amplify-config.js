// Optional runtime config for the AWS deployment (Amplify Hosting + Cognito).
// Locally this file leaves apiBase empty so the app talks to the same origin.
//
// To enable Cognito sign-in on AWS, fill these from the CloudFormation/SAM
// stack outputs, then redeploy the API with RequireAuth=true:
//   apiBase           <- ApiUrl output
//   cognito.hostedUi  <- CognitoHostedUiUrl output (base domain, no /login)
//   cognito.client_id <- UserPoolClientId output
// The app appends "/login?response_type=token&...&scope=openid email profile"
// and reads the returned access token from the URL hash.
window.BB_CONFIG = {
  apiBase: "",
  cognito: null,
  // Example (uncomment and fill after deploying):
  // cognito: {
  //   hostedUi: "https://breathebuddy-123456789012-prod.auth.ap-south-1.amazoncognito.com",
  //   client_id: "1a2b3c4d5e6f7g8h9i0j"
  // }
};
