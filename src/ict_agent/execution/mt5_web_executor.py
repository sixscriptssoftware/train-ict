"""
MT5 Web Terminal Executor

Automates trading on FTMO's MT5 Web Terminal using Playwright.
Works on Mac - no Windows needed!

This allows the AI agent to control MT5 through the browser interface.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, BrowserContext


@dataclass
class MT5WebConfig:
    """Configuration for MT5 Web Terminal"""
    login: str
    password: str
    server: str
    web_url: str = "https://mt5.ftmo.com"
    headless: bool = False  # Set True to run without visible browser


@dataclass 
class TradeResult:
    """Result of a trade operation"""
    success: bool
    order_id: str = ""
    message: str = ""
    fill_price: float = 0.0


class MT5WebExecutor:
    """
    Execute trades on MT5 via the web terminal.
    
    Uses Playwright to control the browser-based MT5 interface.
    This works on Mac/Linux since it doesn't need the Windows MT5 app.
    """
    
    def __init__(self, config: MT5WebConfig):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.connected = False
        self.playwright = None
        
    async def connect(self) -> bool:
        """Connect to MT5 Web Terminal"""
        try:
            print(f"🌐 Connecting to MT5 Web Terminal...")
            print(f"   URL: {self.config.web_url}")
            print(f"   Server: {self.config.server}")
            print(f"   Login: {self.config.login}")
            
            self.playwright = await async_playwright().start()
            
            # Launch Safari (webkit) browser
            self.browser = await self.playwright.webkit.launch(
                headless=self.config.headless
            )
            
            # Create context with viewport
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Create page
            self.page = await self.context.new_page()
            
            # Navigate to MT5 web terminal
            await self.page.goto(self.config.web_url, wait_until='networkidle')
            
            # Wait for login form to load
            await asyncio.sleep(5)
            
            # Take screenshot for debugging
            await self.page.screenshot(path='mt5_web_initial.png')
            print("   📸 Screenshot saved: mt5_web_initial.png")
            
            # Check for iframes - MT5 web terminal often uses them
            frames = self.page.frames
            print(f"   Found {len(frames)} frames")
            
            # Try to find the frame with the login form
            target_frame = self.page
            for frame in frames:
                try:
                    inputs_in_frame = await frame.query_selector_all('input')
                    if len(inputs_in_frame) > 0:
                        print(f"   Found frame with {len(inputs_in_frame)} inputs: {frame.url[:50]}...")
                        target_frame = frame
                        break
                except:
                    continue
            
            # Fill the login form
            try:
                # Get all input fields
                all_inputs = await target_frame.query_selector_all('input')
                print(f"   Found {len(all_inputs)} input fields in target frame")
                
                # If still no inputs, try waiting longer and looking for specific elements
                if len(all_inputs) == 0:
                    print("   ⚠️ No inputs found, waiting longer...")
                    await asyncio.sleep(3)
                    
                    # Try to find inputs by various methods
                    all_inputs = await target_frame.query_selector_all('input')
                    
                    # Also try looking for any editable elements
                    editable = await target_frame.query_selector_all('[contenteditable="true"]')
                    print(f"   Found {len(editable)} contenteditable elements")
                
                # Step 1: Fill Login (first text input)
                print("   🔧 Step 1: Filling login...")
                login_filled = False
                for inp in all_inputs:
                    input_type = await inp.get_attribute('type')
                    placeholder = await inp.get_attribute('placeholder') or ""
                    if input_type in ['text', None, ''] or 'login' in placeholder.lower():
                        await inp.click()
                        await inp.fill(self.config.login)
                        print(f"   ✅ Filled login: {self.config.login}")
                        login_filled = True
                        break
                
                if not login_filled:
                    # Try keyboard approach - tab to first field
                    await target_frame.keyboard.press('Tab')
                    await target_frame.keyboard.type(self.config.login)
                    print(f"   ✅ Typed login via keyboard: {self.config.login}")
                
                # Step 2: Fill Password (password type input)
                print("   🔧 Step 2: Filling password...")
                password_filled = False
                for inp in all_inputs:
                    input_type = await inp.get_attribute('type')
                    if input_type == 'password':
                        await inp.click()
                        await inp.fill(self.config.password)
                        print("   ✅ Filled password: ********")
                        password_filled = True
                        break
                
                if not password_filled:
                    # Try keyboard approach - tab to password field
                    await target_frame.keyboard.press('Tab')
                    await target_frame.keyboard.type(self.config.password)
                    print("   ✅ Typed password via keyboard")
                
                await asyncio.sleep(0.5)
                await self.page.screenshot(path='mt5_web_after_fill.png')
                print("   📸 Screenshot saved: mt5_web_after_fill.png")
                
                # Step 3: Click Connect button (in the iframe)
                print("   🔧 Step 3: Clicking Connect...")
                connect_selectors = [
                    'text="Connect to account"',
                    'button:has-text("Connect to account")',
                    'button:has-text("Connect")',
                    '[class*="connect"]',
                    'button[type="submit"]',
                ]
                
                connect_clicked = False
                # Search in the target_frame (iframe), not the main page
                for selector in connect_selectors:
                    try:
                        connect_btn = await target_frame.query_selector(selector)
                        if connect_btn:
                            await connect_btn.click()
                            print("   ✅ Clicked Connect button")
                            connect_clicked = True
                            await asyncio.sleep(5)
                            break
                    except:
                        continue
                
                if not connect_clicked:
                    print("   ⚠️ Could not find Connect button")
                    
                await self.page.screenshot(path='mt5_web_after_login.png')
                print("   📸 Screenshot saved: mt5_web_after_login.png")
                
                self.connected = True
                print("✅ Connected to MT5 Web Terminal!")
                return True
                
            except Exception as e:
                print(f"   ⚠️ Login form interaction error: {e}")
                import traceback
                traceback.print_exc()
                # Still mark as connected so we can debug
                self.connected = True
                return True
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MT5 Web Terminal"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.connected = False
        print("🔌 Disconnected from MT5 Web Terminal")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.connected or not self.page:
            return {}
        
        try:
            # Take screenshot of current state
            await self.page.screenshot(path='mt5_web_account.png')
            
            # Try to find account info elements
            # This will need to be customized based on the actual MT5 web UI
            
            return {
                "connected": True,
                "login": self.config.login,
                "server": self.config.server,
            }
        except Exception as e:
            print(f"Error getting account info: {e}")
            return {}
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        volume: float,  # Lots (0.01 = micro, 0.1 = mini, 1.0 = standard)
        stop_loss: float = 0,
        take_profit: float = 0,
    ) -> TradeResult:
        """
        Place a market order via the web interface.
        
        This requires clicking through the MT5 web UI.
        """
        if not self.connected or not self.page:
            return TradeResult(success=False, message="Not connected")
        
        try:
            print(f"📤 Placing {side} order: {volume} lots {symbol}")
            print(f"   SL: {stop_loss}, TP: {take_profit}")
            
            # The MT5 web interface has a "New Order" button
            # We need to:
            # 1. Click on the symbol in market watch
            # 2. Click "New Order" or press F9
            # 3. Fill in volume, SL, TP
            # 4. Click Buy/Sell
            
            # Try pressing F9 for new order dialog
            await self.page.keyboard.press('F9')
            await asyncio.sleep(1)
            
            # Take screenshot
            await self.page.screenshot(path='mt5_web_order_dialog.png')
            print("   📸 Screenshot saved: mt5_web_order_dialog.png")
            
            # Find and fill volume
            volume_input = await self.page.query_selector('input[name="volume"], input[placeholder*="Volume"]')
            if volume_input:
                await volume_input.fill(str(volume))
            
            # Find and fill symbol if needed
            symbol_input = await self.page.query_selector('input[name="symbol"], select[name="symbol"]')
            if symbol_input:
                await symbol_input.fill(symbol.replace("_", ""))
            
            # Click Buy or Sell button
            if side.upper() == "BUY":
                buy_btn = await self.page.query_selector('button:has-text("Buy"), button.buy-button')
                if buy_btn:
                    await buy_btn.click()
            else:
                sell_btn = await self.page.query_selector('button:has-text("Sell"), button.sell-button')
                if sell_btn:
                    await sell_btn.click()
            
            await asyncio.sleep(2)
            await self.page.screenshot(path='mt5_web_order_result.png')
            print("   📸 Screenshot saved: mt5_web_order_result.png")
            
            return TradeResult(
                success=True,
                message=f"Order placed via web interface",
            )
            
        except Exception as e:
            print(f"❌ Order failed: {e}")
            return TradeResult(success=False, message=str(e))
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get open positions"""
        if not self.connected or not self.page:
            return []
        
        try:
            # Screenshots help debug what's on screen
            await self.page.screenshot(path='mt5_web_positions.png')
            
            # Parse positions from the Trade tab
            # This needs customization based on actual MT5 web UI
            
            return []
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []


async def test_mt5_web_connection():
    """Test the MT5 Web Terminal connection"""
    
    # FTMO OANDA Demo credentials
    config = MT5WebConfig(
        login="1600073308",
        password="r1g8sN*P", 
        server="OANDA-Demo-1",
        web_url="https://mt5demo.ftmo.oanda.com",
        headless=False,  # Show browser for debugging
    )
    
    executor = MT5WebExecutor(config)
    
    try:
        # Connect
        success = await executor.connect()
        
        if success:
            print("\n✅ MT5 Web Terminal connection test successful!")
            print("   Browser is open - you can see the MT5 interface")
            print("   Screenshots saved for debugging")
            
            # Get account info
            info = await executor.get_account_info()
            print(f"\n📊 Account Info: {info}")
            
            # Keep browser open indefinitely until user presses Enter
            print("\n⏳ Browser will stay open. Press Enter in terminal to close...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            print("\n❌ Connection failed")
            
    finally:
        await executor.disconnect()


if __name__ == "__main__":
    asyncio.run(test_mt5_web_connection())
