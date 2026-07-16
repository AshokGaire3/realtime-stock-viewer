# 📈 Realtime Stock Viewer

An interactive web-based dashboard for live financial market data. Built with React, TypeScript, and modern web technologies to display real-time stock prices, cryptocurrency data, and dynamic charts.

## ✨ Features

- 📊 **Live Stock Data** - Real-time stock prices from Alpha Vantage & Finnhub APIs
- 💰 **Crypto Tracking** - Live cryptocurrency prices from CoinGecko API  
- 📈 **Interactive Charts** - Historical price charts with multiple timeframes
- 🔍 **Smart Search** - Real-time search with autocomplete
- 📱 **Responsive Design** - Optimized for desktop, tablet, and mobile
- 🎨 **Modern UI** - Clean dark theme with smooth animations

## 🛠️ Tech Stack

- **React 18** + **TypeScript** - Modern frontend framework
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Interactive data visualization
- **Vite** - Fast build tool and dev server
- **Lucide React** - Beautiful icons

## � Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/ashokgaire3/realtime-stock-viewer.git
cd realtime-stock-viewer
```

2. **Install dependencies**
```bash
npm install
```

3. **Set up environment variables** (optional)
```bash
cp .env.example .env
```
Add your API keys to `.env`:
```env
VITE_ALPHA_VANTAGE_API_KEY=your_api_key_here
VITE_FINNHUB_API_KEY=your_api_key_here
```

4. **Start the development server**
```bash
npm run dev
```

Visit `http://localhost:5173` to view the dashboard.

## 🔑 API Keys (Optional)

The app works with demo data, but for live data get free API keys:
- [Alpha Vantage](https://www.alphavantage.co/support/#api-key) - Stock market data
- [Finnhub](https://finnhub.io/register) - Additional stock data
- CoinGecko API - No key required for crypto data

## 📦 Build & Deploy

```bash
npm run build
```

Deploy the `dist/` folder to any static hosting service like Netlify, Vercel, or GitHub Pages.

## � Key Features

- **Market Overview** - Real-time market summary and top movers
- **Stock Cards** - Detailed stock information with live updates  
- **Crypto Cards** - Cryptocurrency prices and 24h changes
- **Price Charts** - Interactive historical price visualization
- **Filtering & Sorting** - Advanced data filtering options
- **Mobile Responsive** - Works seamlessly on all devices

## 📄 License

MIT License - feel free to use this project for learning or portfolio purposes!

---

**Built with ❤️ by [Ashok Gaire](https://github.com/ashokgaire3)**
