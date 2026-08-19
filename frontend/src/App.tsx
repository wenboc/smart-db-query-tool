import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import { Dashboard } from "./views/Dashboard";

const appTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#00d4ff", light: "#33ddff", dark: "#0099bb" },
    secondary: { main: "#7c4dff", light: "#b47cff", dark: "#3f1dcb" },
    background: { default: "#0a0e1a", paper: "#111827" },
    success: { main: "#00e676" },
    error: { main: "#ff5252" },
    warning: { main: "#ffd740" },
    text: { primary: "#e0e0e0", secondary: "#9e9e9e" },
  },
  typography: {
    fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace',
    h4: { fontWeight: 700 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    body2: { fontSize: "0.85rem" },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiTextField: {
      defaultProps: { variant: "outlined", size: "small" },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <Dashboard />
    </ThemeProvider>
  );
}

export default App;
