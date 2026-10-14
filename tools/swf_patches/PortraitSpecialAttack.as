package GUI
{
   import GUI.attachables.AttachableTooltip;
   import caurina.transitions.Tweener;
   import core.Base;
   import core.Constants;
   import core.Language;
   import core.NumberParticle;
   import core.SpecialUnitAttack;
   import core.isoengine.IsoInteractiveElement;
   import core.isoengine.IsoSpecialUnit;
   import flash.display.MovieClip;
   import flash.display.Stage;
   import flash.events.KeyboardEvent;
   import flash.events.MouseEvent;
   import flash.events.TimerEvent;
   import flash.filters.GlowFilter;
   import flash.text.TextField;
   import flash.text.TextFieldAutoSize;
   import flash.text.TextFieldType;
   import flash.text.TextFormat;
   import flash.text.TextFormatAlign;
   import flash.utils.Timer;
   import flash.utils.getTimer;
   import managers.ImageManager;
   import managers.images.ImageManagerResource;
   import utils.TextFieldUtil;
   
   public class PortraitSpecialAttack extends Portrait
   {
      
      protected var counterMc:MovieClip;
      
      public var castingMask:MovieClip;
      
      protected var numAttacks:int;
      
      protected var tTimer:Timer;
      
      protected var oAttack:SpecialUnitAttack;
      
      protected var bEnabled:Boolean;
      
      // Seconds left before the attack can be used again (casting + cooldown), shown on the portrait
      protected var secondsTxt:TextField;
      
      protected var readyAt:int = 0;
      
      protected var secondsTimer:Timer;
      
      // Keys 1-9 use the attacks of the selected special unit, in the order of their portraits
      private static var shortcutsInstalled:Boolean = false;
      
      public function PortraitSpecialAttack(param1:SpecialUnitAttack, param2:IsoSpecialUnit, param3:PortraitMC = null)
      {
         super();
         this.eElement = param2;
         this.oAttack = param1;
         this.counterMc = this.portraitMC.addChild(new GiftCounter()) as MovieClip;
         if(this.oAttack.numAttacks == -1)
         {
            this.counterMc.visible = false;
         }
         this.counterMc.x = 43;
         this.counterMc.y = 0;
         this.castingMask = this.portraitMC.addChild(new PortraitCastingMaskMC()) as MovieClip;
         this.castingMask.x = 0;
         this.castingMask.y = 45;
         this.castingMask.scaleY = 0;
         this.castingMask.alpha = 0.9;
         this.numAttacks = this.oAttack.numAttacks;
         this.bEnabled = true;
         this.createSecondsText();
         installShortcuts();
         this.updateAttacks();
         if(this.eElement is IsoSpecialUnit && IsoSpecialUnit(this.eElement).spState != IsoSpecialUnit.SU_STATE_IDLE)
         {
            switch(IsoSpecialUnit(this.eElement).spState)
            {
               case IsoSpecialUnit.SU_STATE_CASTING:
                  this.setStateCasting();
                  break;
               case IsoSpecialUnit.SU_STATE_COOLDOWN:
                  this.setStateCooldown();
            }
         }
      }
      
      override public function clickItem(param1:MouseEvent) : void
      {
         if(IsoSpecialUnit(this.eElement).spState == IsoSpecialUnit.SU_STATE_IDLE || this.oAttack.id == 4)
         {
            if(this.oAttack.numAttacks == -1 || this.oAttack.numAttacks > 0)
            {
               if(IsoSpecialUnit(this.eElement).doAttack(this.oAttack.id))
               {
                  Base.Gui.recuadroInfo.castSpecialAttacks(this.oAttack.castTime,this.oAttack.coolDown);
                  this.updateAttacks();
                  Base.Main.ps.addParticle(new NumberParticle(this.eElement.x * Base.Main.currentZoom + this.eElement.parent.x,this.eElement.y * Base.Main.currentZoom + this.eElement.parent.y,[this.oAttack.attackName],[Constants.TEXT_BLACK],1,this.oAttack.castTime * 30));
               }
               else
               {
                  Base.Main.ps.addParticle(new NumberParticle(this.eElement.x * Base.Main.currentZoom + this.eElement.parent.x,this.eElement.y * Base.Main.currentZoom + this.eElement.parent.y,[this.oAttack.cantMessage],[Constants.TEXT_RED]));
               }
            }
            return;
         }
         Base.Main.ps.addParticle(new NumberParticle(this.eElement.x * Base.Main.currentZoom + this.eElement.parent.x,this.eElement.y * Base.Main.currentZoom + this.eElement.parent.y,[Language.getLiteral(Language.AUX_NO_ESTA_LISTO)],[Constants.TEXT_RED]));
      }
      
      override public function GetElement() : IsoInteractiveElement
      {
         return this.eElement;
      }
      
      public function startCastingMask(param1:int, param2:int) : void
      {
         this.startSeconds(param1 + param2);
         if(Tweener.getTweenCount(this.castingMask) > 0)
         {
            Tweener.removeTweens(this.castingMask);
         }
         Tweener.addTween(this.castingMask,{
            "scaleY":1,
            "time":param1,
            "transition":"linear",
            "onComplete":this.startCoolDown,
            "onCompleteParams":[param2]
         });
      }
      
      private function startCoolDown(param1:int) : void
      {
         if(Tweener.getTweenCount(this.castingMask) > 0)
         {
            Tweener.removeTweens(this.castingMask);
         }
         Tweener.addTween(this.castingMask,{
            "scaleY":0,
            "time":param1,
            "transition":"linear",
            "onComplete":this.setStateIdle
         });
      }
      
      public function updateState() : void
      {
         if(this.eElement is IsoSpecialUnit && IsoSpecialUnit(this.eElement).spState != IsoSpecialUnit.SU_STATE_IDLE)
         {
            switch(IsoSpecialUnit(this.eElement).spState)
            {
               case IsoSpecialUnit.SU_STATE_CASTING:
                  this.setStateCasting();
                  break;
               case IsoSpecialUnit.SU_STATE_COOLDOWN:
                  this.setStateCooldown();
            }
         }
      }
      
      private function setStateCasting() : void
      {
         var _loc3_:Number = NaN;
         var _loc1_:int = IsoSpecialUnit(this.eElement).spTimer;
         var _loc2_:Object = IsoSpecialUnit(this.eElement).spActAttack;
         _loc3_ = _loc1_ / _loc2_.castTime;
         this.castingMask.scaleY = _loc3_;
         this.startSeconds(_loc1_ + int(_loc2_.coolDown));
         if(Tweener.getTweenCount(this.castingMask) > 0)
         {
            Tweener.removeTweens(this.castingMask);
         }
         Tweener.addTween(this.castingMask,{
            "scaleY":0,
            "time":_loc1_,
            "transition":"linear",
            "onComplete":this.startCoolDown,
            "onCompleteParams":[_loc2_.coolDown]
         });
      }
      
      private function setStateCooldown() : void
      {
         var _loc3_:Number = NaN;
         var _loc1_:int = IsoSpecialUnit(this.eElement).spTimer;
         var _loc2_:Object = IsoSpecialUnit(this.eElement).spActAttack;
         _loc3_ = _loc1_ / _loc2_.coolDown;
         this.castingMask.scaleY = _loc3_;
         this.startSeconds(_loc1_);
         if(Tweener.getTweenCount(this.castingMask) > 0)
         {
            Tweener.removeTweens(this.castingMask);
         }
         Tweener.addTween(this.castingMask,{
            "scaleY":0,
            "time":_loc1_,
            "transition":"linear",
            "onComplete":this.setStateIdle
         });
      }
      
      private function setStateIdle() : void
      {
         this.stopSeconds();
         if(Tweener.getTweenCount(this.castingMask) > 0)
         {
            Tweener.removeTweens(this.castingMask);
         }
         this.castingMask.scaleY = 0;
      }
      
      private function createSecondsText() : void
      {
         var fmt:TextFormat = new TextFormat("_sans",20,16777215,true);
         fmt.align = TextFormatAlign.CENTER;
         this.secondsTxt = new TextField();
         this.secondsTxt.defaultTextFormat = fmt;
         this.secondsTxt.selectable = false;
         this.secondsTxt.mouseEnabled = false;
         this.secondsTxt.width = 52;
         this.secondsTxt.height = 28;
         this.secondsTxt.x = 0;
         this.secondsTxt.y = 12;
         this.secondsTxt.filters = [new GlowFilter(0,1,4,4,6)];
         this.secondsTxt.visible = false;
         this.portraitMC.addChild(this.secondsTxt);
      }
      
      private function startSeconds(param1:int) : void
      {
         if(this.secondsTxt == null || param1 <= 0)
         {
            return;
         }
         this.readyAt = getTimer() + param1 * 1000;
         if(this.secondsTimer == null)
         {
            this.secondsTimer = new Timer(200);
            this.secondsTimer.addEventListener(TimerEvent.TIMER,this.onSecondsTick);
         }
         this.secondsTimer.start();
         this.onSecondsTick();
      }
      
      private function onSecondsTick(param1:TimerEvent = null) : void
      {
         var left:int = Math.ceil((this.readyAt - getTimer()) / 1000);
         if(left <= 0)
         {
            this.stopSeconds();
            return;
         }
         this.secondsTxt.text = String(left);
         this.secondsTxt.visible = true;
      }
      
      private function stopSeconds() : void
      {
         if(this.secondsTimer != null)
         {
            this.secondsTimer.stop();
         }
         if(this.secondsTxt != null)
         {
            this.secondsTxt.visible = false;
         }
      }
      
      private static function installShortcuts() : void
      {
         var stage:Stage = null;
         if(shortcutsInstalled)
         {
            return;
         }
         try
         {
            stage = Base.Main.getStage();
         }
         catch(e:Error)
         {
            return;
         }
         if(stage == null)
         {
            return;
         }
         stage.addEventListener(KeyboardEvent.KEY_DOWN,onShortcutKey);
         shortcutsInstalled = true;
      }
      
      private static function onShortcutKey(param1:KeyboardEvent) : void
      {
         var index:int = -1;
         var attacks:Vector.<PortraitSpecialAttack> = null;
         var attack:PortraitSpecialAttack = null;
         var focused:TextField = null;
         try
         {
            focused = Base.Main.getStage().focus as TextField;
            if(focused != null && focused.type == TextFieldType.INPUT)
            {
               return;
            }
            if(param1.ctrlKey || param1.altKey)
            {
               return;
            }
            if(param1.keyCode >= 49 && param1.keyCode <= 57)
            {
               index = int(param1.keyCode - 49);
            }
            else if(param1.keyCode >= 97 && param1.keyCode <= 105)
            {
               index = int(param1.keyCode - 97);
            }
            if(index < 0 || Base.Gui == null || Base.Gui.recuadroInfo == null)
            {
               return;
            }
            attacks = Base.Gui.recuadroInfo.getSpecialAttacks();
            if(attacks == null || index >= attacks.length)
            {
               return;
            }
            attack = attacks[index];
            if(attack == null || attack.stage == null || !attack.visible)
            {
               return;
            }
            attack.clickItem(null);
         }
         catch(e:Error)
         {
         }
      }
      
      private function updateAttacks() : void
      {
         this.oAttack = IsoSpecialUnit(this.eElement).getAttack(this.oAttack.id);
         if(this.oAttack.numAttacks != -1)
         {
            TextFieldUtil.setHTML(this.counterMc.count,this.oAttack.numAttacks);
         }
         else
         {
            TextFieldUtil.setHTML(this.counterMc.count,"u");
         }
      }
      
      override public function UpdateImage() : void
      {
         if(this.portraitMC.image.numChildren <= 0)
         {
            if(this.eElement != null && this.eElement.buildingReference != null)
            {
               this.loadImage(this.oAttack.imgThumb);
            }
         }
      }
      
      override public function loadImage(param1:String) : void
      {
         this.portraitMC.image.addChild(ImageManager.instance.getThumbImage(param1 + ".jpg").getBitmap(52,52,1,ImageManagerResource.ONLY_ADJUST_SIZE));
      }
      
      override public function overItem(param1:MouseEvent = null) : void
      {
         super.overItem(param1);
         if(this.oAttack.attackName == "Dummy Attack" || this.oAttack.attackName == "Minions" || this.oAttack.attackName == null)
         {
            return;
         }
         AttachableTooltip.instance.attachTooltipTo(this,this.oAttack.attackName,AttachableTooltip.TOP);
      }
      
      override public function outItem(param1:MouseEvent = null) : void
      {
         super.outItem(param1);
         AttachableTooltip.instance.dettach();
      }
   }
}

