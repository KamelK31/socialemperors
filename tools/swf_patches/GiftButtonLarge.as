package GUI
{
   import core.*;
   import core.statics.*;
   import flash.display.*;
   import flash.events.*;
   import flash.net.*;
   import flash.system.*;
   import flash.text.*;
   import managers.ImageManager;
   import managers.SoundManager;
   import managers.images.ImageManagerResource;
   import utils.TextFieldUtil;
   
   public class GiftButtonLarge extends GiftButtonMC
   {
      
      Security.allowDomain("*");
      
      public var buttons:Array = new Array(0);
      
      private var bmp:Sprite = null;
      
      private var item:StoreObject;
      
      private var avatar:Loader = new Loader();
      
      private var itemWindow:*;
      
      private var currentSheet:* = null;
      
      private var mapMain:*;
      
      public var popupWindow:* = null;
      
      public function GiftButtonLarge(param1:*, param2:StoreObject, param3:int = 0, param4:int = 0, param5:int = 0)
      {
         super();
         this.itemWindow = param1;
         x = param3;
         y = param4;
         TextFieldUtil.setHTML(counter.count,String(param5));
         TextFieldUtil.setHTML(sell.getChildByName("lbl"),Language.getLiteral(Language.POPUP_STORAGE_SELL));
         TextFieldUtil.setHTML(useButton.getChildByName("lbl"),Language.getLiteral(Language.POPUP_STORAGE_USE));
         this.setItem(param2,param5);
         this.formatSellUseBtns();
      }
      
      public function formatSellUseBtns() : void
      {
         if(this.item == null)
         {
            return;
         }
         if(this.item.staticData.id == Constants.ID_BUILDING_BAHAMUT_HEART)
         {
            sell.visible = false;
            useButton.visible = false;
         }
         else if(this.item.staticData.subcat_functional == Constants.SUBCATFUNC_BUILDING_SPECIAL_COLLECTION)
         {
            sell.visible = false;
            useButton.visible = false;
         }
         else if(this.item.staticData.subcat_functional == Constants.SUBCATFUNC_BUILDING_TOWNHALL)
         {
            sell.visible = false;
            this.enableButton(useButton,this.mouseUsed);
         }
         else if(this.item.staticData.type == "p")
         {
            sell.visible = false;
            useButton.visible = true;
            this.enableButton(useButton,this.mouseUsed);
         }
         else
         {
            sell.visible = true;
            useButton.visible = true;
            this.enableButton(sell,this.sellGift);
            this.enableButton(useButton,this.mouseUsed);
         }
      }
      
      private function disableButtons() : *
      {
      }
      
      public function closeWindow(... rest) : *
      {
         this.disableButtons();
         parent.removeChild(this);
      }
      
      private function mouseUsed(... rest) : *
      {
         var _loc2_:int = 0;
         if(this.item.staticData.type == "p")
         {
            _loc2_ = this.item.staticData.pack_num;
            Base.PopUp.openPopupPacks(_loc2_);
            return;
         }
         if(this.item.staticData.race != Base.Player.currentRace && this.item.staticData.race != Constants.FACTION_NEUTRAL && this.item.staticData.race != Constants.FACTION_ALL)
         {
            Base.PopUp.alert(Language.getLiteral(Language.AVISO_REGALO_FACCION));
            return;
         }
         Base.Main.placingStoreObject = this.item;
         Base.Sound.playSfx(SoundManager.SFX_BUTTON_CLICK);
         Base.Main.setBuilding(this.item.staticData);
      }
      
      public function destroy() : *
      {
         holder.removeEventListener(MouseEvent.CLICK,this.mouseUsed);
         this.disableButton(useButton,this.mouseUsed);
         this.disableButton(sell,this.sellGift);
         parent.removeChild(this);
      }
      
      public function setItem(param1:StoreObject, param2:int = 0) : *
      {
         var _loc3_:TextFormat = null;
         if(param1.staticData.name.length > 11)
         {
            _loc3_ = new TextFormat(null,11);
         }
         this.item = param1;
         counter.visible = param2 > 1;
         TextFieldUtil.setHTML(counter.count,String(param2));
         TextFieldUtil.setHTML(itemName,this.item.staticData.name,"",_loc3_);
         this.setImage();
      }
      
      private function setOptions(... rest) : *
      {
         this.itemWindow.setItem(this.item);
         this.itemWindow.setOptions(this);
      }
      
      private function setImage() : *
      {
         if(this.bmp != null)
         {
            holder.removeChild(this.bmp);
            this.bmp = null;
         }
         this.bmp = new Sprite();
         this.bmp.addChild(ImageManager.instance.getThumbImage(this.item.staticData.img_name + ".jpg").getRealSizeBitmap(ImageManagerResource.ONLY_ADJUST_SIZE));
         holder.addChild(this.bmp);
         holder.buttonMode = true;
         holder.addEventListener(MouseEvent.MOUSE_DOWN,this.mouseUsed);
      }
      
      private function sellGiftReally() : void
      {
         if(this.item.giftId)
         {
            Base.Commands.addCommand({
               "cmd":Constants.CMD_SELL_GIFT,
               "args":[this.item.staticData.id,Base.Main.townID]
            });
         }
         else if(this.item.iphoneId)
         {
            Base.Commands.addCommand({
               "cmd":Constants.CMD_SELL_IPHONE_ITEM,
               "args":[this.item.staticData.id,Base.Main.townID]
            });
         }
         else
         {
            Base.Commands.addCommand({
               "cmd":Constants.CMD_SELL_STORED,
               "args":[this.item.staticData.id,Base.Main.townID]
            });
         }
         Base.Main.removeGift(this.item);
      }
      
      // Copies of this item in the storage (what the counter shows)
      private function sameItems() : Array
      {
         var list:Array = [];
         var gift:StoreObject = null;
         var gifts:Array = Base.Main.gifts;
         var i:int = 0;
         while(i < gifts.length)
         {
            gift = gifts[i] as StoreObject;
            if(gift != null && gift.staticData.id == this.item.staticData.id && Boolean(gift.iphoneId) == Boolean(this.item.iphoneId))
            {
               list.push(gift);
            }
            i++;
         }
         return list;
      }
      
      private function sellValue() : int
      {
         if(Config.SELL_FOR_ZERO_CASH && this.item.staticData.cost_type == CostType.CASH)
         {
            return 0;
         }
         if(this.item.staticData.id == Constants.ID_BUILDING_ZEPPELIN_TOWER || this.item.staticData.id == Constants.ID_BUILDING_DOCK)
         {
            return 0;
         }
         return Math.floor(this.item.staticData.cost / Config.DIVISOR_SELL);
      }
      
      private function resourceName(param1:String) : String
      {
         switch(param1)
         {
            case CostType.CASH:
               return "cash";
            case "w":
               return "wood";
            case "s":
               return "stone";
            case "f":
               return "food";
            default:
               return "gold";
         }
      }
      
      // Sell button: with several copies, ask whether to sell them all (Yes) or only one (No)
      private function sellGift(... rest) : *
      {
         var copies:Array = this.item.iphoneId ? [] : this.sameItems();
         if(copies.length > 1)
         {
            Base.PopUp.confirm("Sell all " + copies.length + " " + this.item.staticData.name + " for " + this.sellValue() * copies.length + " " + this.resourceName(this.item.staticData.cost_type) + "?<br>No = sell only one.",this.sellAll,this.sellOne);
            return;
         }
         this.sellOne();
      }
      
      // Same as selling them one by one: one command per copy, same price each
      private function sellAll() : void
      {
         var copies:Array = this.sameItems();
         var gift:StoreObject = null;
         var value:int = this.sellValue();
         var total:int = 0;
         var gifts:Array = Base.Main.gifts;
         var i:int = 0;
         while(i < copies.length)
         {
            gift = copies[i] as StoreObject;
            if(value > 0)
            {
               Base.Player.adjustStatByType(value,this.item.staticData.cost_type,0);
               total += value;
            }
            if(gift.giftId)
            {
               Base.Commands.addCommand({
                  "cmd":Constants.CMD_SELL_GIFT,
                  "args":[gift.staticData.id,Base.Main.townID]
               });
            }
            else
            {
               Base.Commands.addCommand({
                  "cmd":Constants.CMD_SELL_STORED,
                  "args":[gift.staticData.id,Base.Main.townID]
               });
            }
            var at:int = gifts.indexOf(gift);
            if(at >= 0)
            {
               gifts.splice(at,1);
            }
            i++;
         }
         if(total > 0)
         {
            Base.Main.ps.addParticle(new NumberParticle(355,450,[total],[this.item.staticData.cost_type],2));
         }
         Base.Gui.resetWindow();
      }
      
      private function sellOne() : void
      {
         if(Config.SELL_FOR_ZERO_CASH && this.item.staticData.cost_type == CostType.CASH)
         {
            Base.PopUp.confirm(Language.getLiteral(Language.INFO_CONFIRMAR_VENTA,[0,"cash"]),this.sellGiftReally,null);
         }
         else
         {
            if(this.item.staticData.id != Constants.ID_BUILDING_ZEPPELIN_TOWER && this.item.staticData.id != Constants.ID_BUILDING_DOCK)
            {
               Base.Player.adjustStatByType(Math.floor(this.item.staticData.cost / Config.DIVISOR_SELL),this.item.staticData.cost_type,0);
               Base.Main.ps.addParticle(new NumberParticle(355,450,[Math.floor(this.item.staticData.cost / Config.DIVISOR_SELL)],[this.item.staticData.cost_type],2));
            }
            this.sellGiftReally();
         }
      }
      
      private function gotoInvite(... rest) : *
      {
      }
      
      public function closePopup() : *
      {
         if(this.popupWindow != null)
         {
            this.popupWindow.closeWindow();
         }
      }
      
      public function ioErrorHandler(param1:*) : *
      {
      }
      
      private function enableButton(param1:*, param2:Function) : *
      {
         param1.hitZone.buttonMode = true;
         param1.hitZone.addEventListener(MouseEvent.CLICK,param2);
         param1.hitZone.addEventListener(MouseEvent.ROLL_OVER,GameStatic.startFloat);
         param1.hitZone.addEventListener(MouseEvent.ROLL_OUT,GameStatic.stopFloat);
      }
      
      private function disableButton(param1:*, param2:Function) : *
      {
         param1.hitZone.buttonMode = false;
         param1.hitZone.removeEventListener(MouseEvent.CLICK,param2);
         param1.hitZone.removeEventListener(MouseEvent.ROLL_OVER,GameStatic.startFloat);
         param1.hitZone.removeEventListener(MouseEvent.ROLL_OUT,GameStatic.stopFloat);
      }
      
      private function enableButtons() : *
      {
      }
   }
}

