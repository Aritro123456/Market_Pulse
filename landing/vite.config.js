import { defineConfig } from 'vite';
export default defineConfig({base:'./',build:{outDir:'../web',emptyOutDir:false},server:{proxy:{'/terminal.html':'http://127.0.0.1:8000','/api':'http://127.0.0.1:8000'}}});
