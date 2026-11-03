import { StrictMode } from 'react'; // Loads React's extra development checks.
import { createRoot } from 'react-dom/client'; // Connects React to the page.
import { BrowserRouter, Route, Routes } from 'react-router-dom'; // Supplies distinct URLs for account screens.
import App from './App'; // Imports the main application screen.
import AuthPages from './AuthPages'; // Imports account creation and recovery screens.
import './style.css'; // Loads the visual design system.

createRoot(document.getElementById('root')!).render( // Starts the application inside the root element.
  <StrictMode> {/* Keeps development checks enabled. */}
    <BrowserRouter> {/* Enables links that work on direct page visits and refreshes. */}
      <Routes> {/* Select the screen from the current URL path. */}
        <Route path="/" element={<App />} /> {/* Keep recipe discovery on the home route. */}
        <Route path="*" element={<AuthPages />} /> {/* Use the account page component for auth URLs. */}
      </Routes> {/* Finish the route table. */}
    </BrowserRouter> {/* Finish browser navigation support. */}
  </StrictMode>, // Closes the React development wrapper.
); // Completes the render call.
