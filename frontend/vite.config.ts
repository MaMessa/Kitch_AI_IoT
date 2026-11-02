import { defineConfig } from 'vite'; // Imports Vite configuration helper.
import react from '@vitejs/plugin-react'; // Enables React JSX support.

export default defineConfig({ plugins: [react()] }); // Exports the React-enabled development setup.
