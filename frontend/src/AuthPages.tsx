// Import React's form event type and state helpers for the account screens. // Explain the purpose of the React imports.
import { useState, type FormEvent, type ReactNode } from 'react'; // Keep form values and feedback inside this page.
// Import React Router helpers for navigation and URL query parameters. // Explain the routing imports.
import { Link, useLocation, useNavigate } from 'react-router-dom'; // Connect account actions to browser URLs.
// Keep local development pointed at the same loopback host as the API. // Explain why the API origin is fixed for this prototype.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'; // Use Vite's same-origin proxy locally and allow a production API URL later.

// Describe the success response used by the account endpoints. // Explain the response type.
type ApiMessage = { message: string }; // Represent generic email-flow feedback.

// Send one JSON request with the browser session cookie enabled. // Explain the shared API helper.
async function sendJson<T>(path: string, payload: Record<string, string>): Promise<T> { // Reuse consistent API behavior for every auth form.
  const response = await fetch(`${API_BASE_URL}${path}`, { // Send the request to the matching FastAPI route.
    method: 'POST', // Use POST because these endpoints change account state.
    credentials: 'include', // Let the browser save and send the HttpOnly session cookie.
    headers: { 'Content-Type': 'application/json' }, // Tell FastAPI that the body contains JSON.
    body: JSON.stringify(payload), // Encode form values using the API's request schema.
  }); // Finish the fetch options.
  const responseBody = await response.json().catch(() => ({})) as { detail?: string; message?: string }; // Read JSON when present and tolerate an empty response.
  if (!response.ok) { // Translate API failures into readable form feedback.
    throw new Error(responseBody.detail ?? responseBody.message ?? 'Une erreur est survenue. Réessaie.'); // Prefer the API explanation and use a safe fallback.
  } // Finish API error handling.
  return responseBody as T; // Return the successful response in the requested shape.
} // Finish the reusable API helper.

// Render login, registration, verification, and password recovery screens. // Explain the responsibility of the page component.
export default function AuthPages() { // Select the account screen from the current URL.
  const location = useLocation(); // Read the path and token query parameter.
  const navigate = useNavigate(); // Move the browser after successful account actions.
  const token = new URLSearchParams(location.search).get('token') ?? ''; // Read a one-time link token from the email URL.
  const page = location.pathname; // Keep the path available for page-specific behavior.
  const isRegister = page === '/register'; // Detect account creation.
  const isVerify = page === '/verify-email'; // Detect email verification.
  const isForgot = page === '/forgot-password'; // Detect the password recovery request page.
  const isReset = page === '/reset-password'; // Detect the password replacement page.
  const [firstName, setFirstName] = useState(''); // Store the required registration name.
  const [email, setEmail] = useState(''); // Store the email entered by the visitor.
  const [password, setPassword] = useState(''); // Store the current or new password while the page is open.
  const [message, setMessage] = useState(''); // Show successful account actions.
  const [error, setError] = useState(''); // Show API or validation errors.
  const [busy, setBusy] = useState(false); // Prevent duplicate submissions while a request is running.
  const pageTitle = isRegister ? 'Créer ton compte' : isForgot ? 'Mot de passe oublié' : isReset ? 'Nouveau mot de passe' : isVerify ? 'Vérifier ton email' : 'Content de te revoir'; // Match the heading to the selected route.
  const pageIntro = isRegister ? 'Retrouve tes recettes et construis ton carnet de cuisine.' : isForgot ? 'On t’enverra un lien pour choisir un nouveau mot de passe.' : isReset ? 'Choisis un nouveau mot de passe pour ton compte KitchAI.' : isVerify ? 'Confirme ton adresse pour terminer la vérification.' : 'Connecte-toi pour retrouver tes recettes.'; // Give the screen a short explanation.

  // Submit the current account action to its matching API endpoint. // Explain the shared form submission flow.
  async function handleSubmit(event: FormEvent<HTMLFormElement>) { // Keep form submission inside React.
    event.preventDefault(); // Stop the browser from reloading before the API responds.
    setError(''); // Clear any error from a previous attempt.
    setMessage(''); // Clear any old success message.
    setBusy(true); // Disable form submission until this request completes.
    try { // Handle success and API errors in one place.
      if (isRegister) { // Create an account and request an email verification link.
        const result = await sendJson<{ email: string }>('/auth/register', { first_name: firstName, email, password }); // Register and start the browser session.
        setMessage(`Compte créé pour ${result.email}. Consulte ta boîte mail pour vérifier l’adresse.`); // Tell the user where to find the next step.
      } else if (isForgot) { // Start a password recovery request.
        const result = await sendJson<ApiMessage>('/auth/password/forgot', { email }); // Ask the API to email a reset link when the account exists.
        setMessage(result.message); // Show the generic anti-enumeration response.
      } else if (isReset) { // Complete password recovery using the email token.
        const result = await sendJson<ApiMessage>('/auth/password/reset', { token, new_password: password }); // Change the password and revoke older sessions.
        setMessage(result.message); // Confirm the password change.
      } else { // Sign in with an existing email and password.
        await sendJson('/auth/login', { email, password }); // Establish the browser session cookie.
        navigate('/'); // Return the signed-in visitor to recipe discovery.
      } // Finish the action-specific request.
    } catch (requestError) { // Convert network and API errors into page feedback.
      setError(requestError instanceof Error ? requestError.message : 'Impossible de joindre KitchAI. Vérifie que l’API est démarrée.'); // Explain the failure without exposing implementation details.
    } finally { // Always restore the form after the request ends.
      setBusy(false); // Re-enable controls for another attempt.
    } // Finish request lifecycle handling.
  } // Finish the form submission function.

  // Verify the email only after the visitor explicitly presses the confirmation button. // Avoid one-time link consumption by automatic email scanners.
  async function handleVerify() { // Submit the one-time email verification token.
    setError(''); // Clear an earlier verification failure.
    setMessage(''); // Clear any earlier verification success.
    setBusy(true); // Prevent repeated clicks during the request.
    try { // Handle the verification response.
      const result = await sendJson<ApiMessage>('/auth/email/verify', { token }); // Ask the API to consume the one-time token.
      setMessage(result.message); // Show that the email address is verified.
    } catch (requestError) { // Show expired, invalid, or network errors.
      setError(requestError instanceof Error ? requestError.message : 'Impossible de vérifier cette adresse.'); // Give the user a safe explanation.
    } finally { // Restore the button after the API call.
      setBusy(false); // Allow retry or navigation.
    } // Finish verification request handling.
  } // Finish the verification function.

  // Request a replacement verification link when registration delivery failed or the link expired. // Explain the resend action.
  async function handleResendVerification() { // Submit the email to the neutral resend endpoint.
    setError(''); // Clear any previous error message.
    setBusy(true); // Prevent duplicate email requests while the endpoint responds.
    try { // Ask the API to send a fresh link if the account needs verification.
      const result = await sendJson<ApiMessage>('/auth/email/resend', { email }); // Request a new verification link.
      setMessage(result.message); // Show the same response whether or not the account exists.
    } catch (requestError) { // Convert connection problems to simple feedback.
      setError(requestError instanceof Error ? requestError.message : 'Impossible de demander un nouvel email.'); // Explain that the request could not complete.
    } finally { // Restore the resend control.
      setBusy(false); // Allow another attempt.
    } // Finish resend request handling.
  } // Finish the resend function.

  // Show the one-time confirmation action instead of consuming the token on page load. // Explain the verification page behavior.
  if (isVerify) { // Render the verification-specific action page.
    return ( // Begin the verification screen markup.
      <AuthLayout title={pageTitle} intro={pageIntro}> {/* Reuse the branded auth frame. */}
        {!token && <p className="auth-error" role="alert">Le lien ne contient pas de jeton. Demande un nouvel email de vérification.</p>} {/* Explain a missing link token. */}
        {message && <p className="auth-success" role="status">{message}</p>} {/* Announce successful verification. */}
        {error && <p className="auth-error" role="alert">{error}</p>} {/* Announce a verification error. */}
        {token && !message && <button className="auth-submit" type="button" disabled={busy} onClick={handleVerify}>{busy ? 'Vérification…' : 'Confirmer mon adresse email'}</button>} {/* Verify only after a deliberate click. */}
        {(!token || error) && <form className="auth-form" onSubmit={(event) => { event.preventDefault(); void handleResendVerification(); }}><label>Adresse email<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label><button className="auth-secondary" type="submit" disabled={busy}>{busy ? 'Envoi…' : 'Renvoyer un lien'}</button></form>} {/* Let the user recover from an expired or missing verification link. */}
        <p className="auth-footnote"><Link to="/login">Retour à la connexion</Link></p> {/* Return to sign-in. */}
      </AuthLayout>
    ); // Return the verification page.
  } // Finish the verification route branch.

  // Render the current form with only fields required by its action. // Explain the reusable form markup.
  return ( // Begin the account form screen.
    <AuthLayout title={pageTitle} intro={pageIntro}> {/* Apply the KitchAI visual frame. */}
      {error && <p className="auth-error" role="alert">{error}</p>} {/* Announce server or network errors. */}
      {message && <p className="auth-success" role="status">{message}</p>} {/* Announce completed actions. */}
      {message && isRegister && <button className="auth-secondary" type="button" disabled={busy} onClick={handleResendVerification}>Renvoyer le lien de vérification</button>} {/* Let a new user request a replacement email. */}
      {!message && <form className="auth-form" onSubmit={handleSubmit}> {/* Hide the form after a successful action. */}
        {isRegister && <label>Prénom<input autoComplete="given-name" required maxLength={100} value={firstName} onChange={(event) => setFirstName(event.target.value)} /></label>} {/* Collect the required first name at registration. */}
        {!isReset && <label>Adresse email<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>} {/* Collect the email for account actions. */}
        {!isForgot && <label>{isReset ? 'Nouveau mot de passe' : 'Mot de passe'}<input type="password" autoComplete={isReset ? 'new-password' : isRegister ? 'new-password' : 'current-password'} required minLength={isRegister || isReset ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{(isRegister || isReset) && <small>12 caractères minimum.</small>}</label>} {/* Apply the API's password constraints. */}
        {isReset && !token && <p className="auth-error" role="alert">Le lien ne contient pas de jeton de réinitialisation.</p>} {/* Explain a missing reset token. */}
        <button className="auth-submit" type="submit" disabled={busy || (isReset && !token)}>{busy ? 'En cours…' : isRegister ? 'Créer mon compte' : isForgot ? 'Envoyer le lien' : isReset ? 'Modifier mon mot de passe' : 'Me connecter'}</button> {/* Send the selected account action. */}
      </form>} {/* Finish the dynamic form. */}
      <div className="auth-footnote">{isRegister ? <>Déjà un compte ? <Link to="/login">Se connecter</Link></> : isForgot ? <>Tu as retrouvé ton mot de passe ? <Link to="/login">Se connecter</Link></> : isReset ? <>Tu peux ensuite <Link to="/login">te connecter</Link>.<br /><Link to="/forgot-password">Demander un autre lien</Link></> : <>Pas encore de compte ? <Link to="/register">Créer un compte</Link><br /><Link to="/forgot-password">Mot de passe oublié ?</Link></>}</div> {/* Keep the related account routes easy to find. */}
    </AuthLayout>
  ); // Return the selected form.
} // Finish the account page component.

// Wrap every account action in the same responsive KitchAI shell. // Explain the shared visual frame.
function AuthLayout({ title, intro, children }: { title: string; intro: string; children: ReactNode }) { // Reuse typography and spacing across auth pages.
  return ( // Begin the shared auth layout.
    <main className="auth-shell"> {/* Center the account card on the dark blue canvas. */}
      <section className="auth-card"> {/* Group brand, title, form, and links. */}
        <Link className="auth-brand" to="/" aria-label="KitchAI, accueil"><span className="brand-mark">K</span><span>Kitch<span className="brand-ai">AI</span></span></Link> {/* Return to discovery from the brand. */}
        <p className="auth-eyebrow">TON CARNET DE CUISINE</p> {/* Repeat the product's small overline style. */}
        <h1>{title}</h1> {/* Display the selected account action. */}
        <p className="auth-intro">{intro}</p> {/* Explain what this page does. */}
        {children} {/* Render the page-specific form or result. */}
      </section> {/* Finish the auth card. */}
    </main>
  ); // Return the reusable auth frame.
} // Finish the shared auth layout component.
