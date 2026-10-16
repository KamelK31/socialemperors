package com.adobe.serialization.json
{
   import flash.utils.getDefinitionByName;
   
   public class JSON
   {
      
      // The player's built-in JSON parser (written in native code) is far faster than the
      // ActionScript JSONDecoder below, which reads the 2 MB game config one character at a time.
      private static var nativeJson:Object = null;
      
      private static var nativeChecked:Boolean = false;
      
      public function JSON()
      {
         super();
      }
      
      public static function encode(param1:Object) : String
      {
         var _loc2_:JSONEncoder = new JSONEncoder(param1);
         return _loc2_.getString();
      }
      
      public static function decode(param1:String) : *
      {
         var parsed:* = undefined;
         if(!nativeChecked)
         {
            nativeChecked = true;
            try
            {
               nativeJson = getDefinitionByName("JSON") as Object;
               if(nativeJson != null && !(nativeJson["parse"] is Function))
               {
                  nativeJson = null;
               }
            }
            catch(e:Error)
            {
               nativeJson = null;
            }
         }
         if(nativeJson != null)
         {
            try
            {
               parsed = nativeJson.parse(param1);
               return parsed;
            }
            catch(e2:Error)
            {
            }
         }
         var _loc2_:JSONDecoder = new JSONDecoder(param1);
         return _loc2_.getValue();
      }
   }
}
