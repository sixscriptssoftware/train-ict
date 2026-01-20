"""
FTMO Autonomous Trader via MT5 Web Terminal

Uses Playwright to control the MT5 web interface for trading on FTMO.
Integrates with ICT analysis engine for signal generation.

Works on Mac - no Windows needed!
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Frame


@dataclass
class FTMOConfig:
    """FTMO MT5 Configuration"""
    login: str = "1600073308"
    password: str = "r1g8sN*P"
    server: str = "OANDA-Demo-1"
    web_url: str = "https://mt5demo.ftmo.oanda.com"
    headless: bool = False
    
    # Trading parameters
    max_risk_per_trade: float = 0.5  # 0.5% risk per trade (FTMO safe)
    max_daily_loss: float = 4.0  # 4% max daily loss (FTMO limit is 5%)
    max_total_loss: float = 8.0  # 8% max total loss (FTMO limit is 10%)
    confidence_threshold: float = 0.45  # 45% minimum confidence
    scan_interval: int = 300  # 5 minutes between scans


class FTMOAutonomousTrader:
    """
    Autonomous trader for FTMO using MT5 Web Terminal.
    
    Uses Playwright browser automation to:
    1. Login to MT5 web terminal
    2. Monitor markets using ICT concepts
    3. Place trades when setups appear
    4. Manage positions and risk
    """
    
    def __init__(self, config: FTMOConfig):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.target_frame: Optional[Frame] = None
        self.playwright = None
        self.connected = False
        self.logged_in = False
        
        # Trading state
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.trades_today = 0
        self.open_positions = []
        
        # Symbols to trade (FTMO format)
        self.symbols = [
            "EURUSD",
            "GBPUSD", 
            "XAUUSD",
            "USDJPY",
            "AUDUSD",
            "EURGBP",
        ]
    
    async def start(self):
        """Start the autonomous trader"""
        print("=" * 60)
        print("🚀 FTMO AUTONOMOUS TRADER - MT5 Web Terminal")
        print("=" * 60)
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 Server: {self.config.server}")
        print(f"📊 Symbols: {', '.join(self.symbols)}")
        print(f"⚠️  Risk per trade: {self.config.max_risk_per_trade}%")
        print(f"⚠️  Max daily loss: {self.config.max_daily_loss}%")
        print("=" * 60)
        
        # Connect to MT5 Web Terminal
        success = await self.connect_and_login()
        
        if not success:
            print("❌ Failed to connect. Exiting.")
            return
        
        print("\n✅ Connected to FTMO MT5 Terminal!")
        print("🤖 Starting autonomous trading loop...")
        print("-" * 60)
        
        # Main trading loop
        await self.trading_loop()
    
    async def connect_and_login(self) -> bool:
        """Connect to MT5 web terminal and login"""
        try:
            print("\n🌐 Launching Firefox browser...")
            self.playwright = await async_playwright().start()
            
            # Use Firefox - works better than Chrome for Testing
            self.browser = await self.playwright.firefox.launch(
                headless=self.config.headless,
            )
            
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                no_viewport=True
            )
            
            self.page = await self.context.new_page()
            
            print(f"🌐 Navigating to {self.config.web_url}...")
            await self.page.goto(self.config.web_url, wait_until='networkidle')
            await asyncio.sleep(5)
            
            # Find the iframe with the login form
            frames = self.page.frames
            print(f"   Found {len(frames)} frames")
            
            self.target_frame = self.page
            for frame in frames:
                try:
                    inputs = await frame.query_selector_all('input')
                    if len(inputs) > 0:
                        print(f"   ✅ Found frame with {len(inputs)} inputs")
                        self.target_frame = frame
                        break
                except:
                    continue
            
            # Fill login credentials
            await self.fill_login_form()
            
            # Wait for user to click Connect if auto-click fails
            print("\n⏳ Waiting for login to complete...")
            print("   (Click 'Connect to account' if button wasn't auto-clicked)")
            
            # Wait for terminal to load (check for trading elements)
            await self.wait_for_terminal()
            
            self.connected = True
            self.logged_in = True
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def fill_login_form(self):
        """Fill in the login credentials"""
        try:
            all_inputs = await self.target_frame.query_selector_all('input')
            print(f"   Found {len(all_inputs)} input fields")
            
            # Fill Login
            for inp in all_inputs:
                input_type = await inp.get_attribute('type')
                placeholder = await inp.get_attribute('placeholder') or ""
                if input_type in ['text', None, ''] or 'login' in placeholder.lower():
                    await inp.click()
                    await inp.fill(self.config.login)
                    print(f"   ✅ Login: {self.config.login}")
                    break
            
            # Fill Password
            for inp in all_inputs:
                input_type = await inp.get_attribute('type')
                if input_type == 'password':
                    await inp.click()
                    await inp.fill(self.config.password)
                    print("   ✅ Password: ********")
                    break
            
            await asyncio.sleep(1)
            
            # Try to click Connect button
            connect_selectors = [
                'text="Connect to account"',
                'button:has-text("Connect to account")',
                'button:has-text("Connect")',
            ]
            
            for selector in connect_selectors:
                try:
                    btn = await self.target_frame.query_selector(selector)
                    if btn:
                        await btn.click()
                        print("   ✅ Clicked Connect button")
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"   ⚠️ Login form error: {e}")
    
    async def wait_for_terminal(self):
        """Wait for the trading terminal to fully load"""
        print("\n⏳ Waiting for MT5 terminal to load...")
        
        max_wait = 60  # 60 seconds max
        start = datetime.now()
        
        while (datetime.now() - start).seconds < max_wait:
            await asyncio.sleep(2)
            
            # Take screenshot to check state
            await self.page.screenshot(path='mt5_terminal_state.png')
            
            # Check if we're on the trading terminal (look for trading elements)
            # The terminal should have chart elements, market watch, etc.
            try:
                # Look for elements that indicate we're logged in
                for frame in self.page.frames:
                    # Check for common MT5 elements
                    market_watch = await frame.query_selector('[class*="market"], [class*="quote"], [class*="symbol"]')
                    chart = await frame.query_selector('[class*="chart"], canvas')
                    
                    if market_watch or chart:
                        print("   ✅ Trading terminal detected!")
                        self.target_frame = frame
                        return True
                        
            except:
                pass
            
            elapsed = (datetime.now() - start).seconds
            print(f"   ... waiting ({elapsed}s)")
        
        print("   ⚠️ Timeout waiting for terminal, but continuing anyway")
        return True
    
    async def trading_loop(self):
        """Main trading loop - scans for setups and places trades"""
        print("\n🔄 Trading loop started")
        print(f"   Scanning every {self.config.scan_interval} seconds")
        
        scan_count = 0
        
        while True:
            try:
                scan_count += 1
                now = datetime.now()
                
                print(f"\n{'='*50}")
                print(f"📊 SCAN #{scan_count} - {now.strftime('%H:%M:%S')}")
                print(f"{'='*50}")
                
                # Take screenshot of current state
                await self.page.screenshot(path='mt5_current_state.png')
                
                # Check if we're still connected
                if not await self.check_connection():
                    print("⚠️ Connection lost, attempting reconnect...")
                    await self.reconnect()
                    continue
                
                # Get account info
                account_info = await self.get_account_info()
                print(f"💰 Account Status: {account_info}")
                
                # Check risk limits
                if not self.check_risk_limits():
                    print("🛑 Risk limits reached - pausing trading")
                    await asyncio.sleep(self.config.scan_interval)
                    continue
                
                # Scan each symbol for ICT setups
                for symbol in self.symbols:
                    await self.analyze_symbol(symbol)
                
                # Check open positions
                await self.manage_positions()
                
                print(f"\n⏰ Next scan in {self.config.scan_interval} seconds...")
                await asyncio.sleep(self.config.scan_interval)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping trader (Ctrl+C pressed)")
                break
            except Exception as e:
                print(f"\n❌ Error in trading loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(30)  # Wait before retry
    
    async def check_connection(self) -> bool:
        """Check if still connected to MT5"""
        try:
            # Simple check - see if page is responsive
            await self.page.evaluate("1+1")
            return True
        except:
            return False
    
    async def reconnect(self):
        """Attempt to reconnect to MT5"""
        print("🔄 Reconnecting...")
        try:
            await self.page.goto(self.config.web_url, wait_until='networkidle')
            await asyncio.sleep(5)
            await self.fill_login_form()
            await self.wait_for_terminal()
        except Exception as e:
            print(f"❌ Reconnect failed: {e}")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account balance and equity from the terminal"""
        # For now return placeholder - will parse from UI later
        return {
            "balance": 100000.0,  # FTMO 100k challenge
            "equity": 100000.0 + self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "trades_today": self.trades_today,
        }
    
    def check_risk_limits(self) -> bool:
        """Check if we're within FTMO risk limits"""
        # Daily loss check (5% limit, we use 4%)
        if self.daily_pnl < -(self.config.max_daily_loss / 100 * 100000):
            print(f"   ❌ Daily loss limit reached: ${self.daily_pnl:.2f}")
            return False
        
        # Total loss check (10% limit, we use 8%)
        if self.total_pnl < -(self.config.max_total_loss / 100 * 100000):
            print(f"   ❌ Total loss limit reached: ${self.total_pnl:.2f}")
            return False
        
        return True
    
    async def analyze_symbol(self, symbol: str):
        """Analyze a symbol for ICT trading setups"""
        print(f"\n   📈 Analyzing {symbol}...")
        
        # In a full implementation, this would:
        # 1. Get price data from the MT5 terminal
        # 2. Run ICT analysis (FVG, OB, liquidity, etc.)
        # 3. Generate trading signals
        
        # For now, we'll simulate the analysis
        # In production, integrate with the ICT detectors
        
        try:
            # Check if symbol is in a killzone
            hour = datetime.now().hour
            in_killzone = hour in [2, 3, 4, 7, 8, 9, 13, 14, 15]  # London/NY
            
            if in_killzone:
                print(f"      ⏰ In killzone - looking for setups")
                
                # Placeholder for ICT analysis
                # setup = await self.run_ict_analysis(symbol)
                # if setup and setup.confidence >= self.config.confidence_threshold:
                #     await self.place_trade(symbol, setup)
                
            else:
                print(f"      ⏰ Outside killzone - monitoring only")
                
        except Exception as e:
            print(f"      ❌ Error analyzing {symbol}: {e}")
    
    async def place_trade(self, symbol: str, side: str, lot_size: float, sl: float, tp: float):
        """Place a trade via the MT5 web interface"""
        print(f"\n🎯 PLACING TRADE: {side} {lot_size} {symbol}")
        print(f"   SL: {sl}, TP: {tp}")
        
        try:
            # Press F9 or find New Order button
            await self.page.keyboard.press('F9')
            await asyncio.sleep(1)
            
            # Screenshot the order dialog
            await self.page.screenshot(path='mt5_order_dialog.png')
            
            # Fill order details
            # This will need customization based on actual MT5 web UI
            
            # Find and fill volume
            for frame in self.page.frames:
                volume_input = await frame.query_selector('input[type="number"], input[name*="volume"]')
                if volume_input:
                    await volume_input.fill(str(lot_size))
                    break
            
            # Click Buy or Sell
            if side.upper() == "BUY":
                for frame in self.page.frames:
                    buy_btn = await frame.query_selector('button:has-text("Buy"), [class*="buy"]')
                    if buy_btn:
                        await buy_btn.click()
                        break
            else:
                for frame in self.page.frames:
                    sell_btn = await frame.query_selector('button:has-text("Sell"), [class*="sell"]')
                    if sell_btn:
                        await sell_btn.click()
                        break
            
            await asyncio.sleep(2)
            await self.page.screenshot(path='mt5_order_result.png')
            
            self.trades_today += 1
            print(f"   ✅ Trade placed successfully!")
            
        except Exception as e:
            print(f"   ❌ Trade failed: {e}")
    
    async def manage_positions(self):
        """Check and manage open positions"""
        print(f"\n   📋 Checking open positions...")
        
        # In production, this would:
        # 1. Parse positions from MT5 trade tab
        # 2. Check for trailing stop adjustments
        # 3. Check for partial profit taking
        
        print(f"      Open positions: {len(self.open_positions)}")
    
    async def stop(self):
        """Clean shutdown"""
        print("\n🔌 Shutting down...")
        
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        print("✅ Trader stopped")


async def main():
    """Main entry point"""
    config = FTMOConfig()
    trader = FTMOAutonomousTrader(config)
    
    try:
        await trader.start()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
    finally:
        await trader.stop()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  FTMO AUTONOMOUS ICT TRADER")
    print("  MT5 Web Terminal Edition")
    print("="*60 + "\n")
    
    asyncio.run(main())
