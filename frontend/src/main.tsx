import { StrictMode } from 'react'; // Loads React's extra development checks.
import { createRoot } from 'react-dom/client'; // Connects React to the page.
import App from './App'; // Imports the main application screen.
import './style.css'; // Loads the visual design system.

createRoot(document.getElementById('root')!).render( // Starts the application inside the root element.
  <StrictMode> {/* Keeps development checks enabled. */}
    <App /> {/* Displays the KitchAI prototype. */}
  </StrictMode>, // Closes the React development wrapper.
); // Completes the render call.
